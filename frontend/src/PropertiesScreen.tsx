import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Table,
  Typography,
} from 'antd'
import { useEffect, useState } from 'react'
import { notifyCatalogChanged } from './catalog'
import {
  createBed,
  createBuilding,
  createFloor,
  createProperty,
  createSpace,
  deleteBed,
  deleteProperty,
  deleteSpace,
  listBeds,
  listBuildings,
  listFloors,
  listProperties,
  listSpaces,
  updateBedAvailability,
  updateSpaceAvailability,
  type BedRecord,
  type BlockReason,
  type BuildingRecord,
  type FloorRecord,
  type PropertyRecord,
  type SpaceKind,
  type SpaceRecord,
} from './api/properties'
import { errorText } from './api/session'

const AVAILABILITY_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'maintenance', label: 'Unavailable for maintenance' },
]

const KIND_OPTIONS = [
  { value: 'room', label: 'Room' },
  { value: 'unit', label: 'Whole unit' },
]

type PropertyValues = { name: string; address?: string }
type NameValues = { name: string }
type FloorValues = { name: string; building_id?: string }
type SpaceValues = {
  name: string
  kind: SpaceKind
  building_id?: string
  floor_id?: string
}

function availabilityChoice(value: string): {
  availability: 'active' | 'inactive' | 'unavailable'
  block_reason: BlockReason
} {
  if (value === 'maintenance') {
    return { availability: 'unavailable', block_reason: 'maintenance' }
  }
  if (value === 'inactive') {
    return { availability: 'inactive', block_reason: '' }
  }
  return { availability: 'active', block_reason: '' }
}

function availabilityValue(record: {
  availability: string
  block_reason: string
}): string {
  if (record.availability === 'unavailable') {
    return 'maintenance'
  }
  return record.availability
}

function kindLabel(kind: SpaceKind): string {
  return kind === 'unit' ? 'Whole unit' : 'Room'
}

function StatusSelect({
  label,
  record,
  onChange,
}: {
  label: string
  record: { availability: string; block_reason: string }
  onChange: (value: string) => void
}) {
  return (
    <Select
      aria-label={label}
      value={availabilityValue(record)}
      options={AVAILABILITY_OPTIONS}
      style={{ width: '100%', marginTop: 8 }}
      onChange={(value) => {
        if (typeof value === 'string') {
          onChange(value)
        }
      }}
    />
  )
}

function PropertyDetail({
  workspaceId,
  property,
  canManage,
  onBack,
  onDeleted,
}: {
  workspaceId: string
  property: PropertyRecord
  canManage: boolean
  onBack: () => void
  onDeleted: () => void
}) {
  const [buildings, setBuildings] = useState<BuildingRecord[] | null>(null)
  const [floors, setFloors] = useState<FloorRecord[] | null>(null)
  const [spaces, setSpaces] = useState<SpaceRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [openSpaceId, setOpenSpaceId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [spaceForm] = Form.useForm<SpaceValues>()
  const selectedBuilding = Form.useWatch('building_id', spaceForm)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      listBuildings(workspaceId, property.id, controller.signal),
      listFloors(workspaceId, property.id, controller.signal),
      listSpaces(workspaceId, property.id, controller.signal),
    ])
      .then(([nextBuildings, nextFloors, nextSpaces]) => {
        if (controller.signal.aborted) {
          return
        }
        setBuildings(nextBuildings)
        setFloors(nextFloors)
        setSpaces(nextSpaces)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setMessage(errorText(error))
      })
    return () => {
      controller.abort()
    }
  }, [property.id, reloadKey, workspaceId])

  function refresh() {
    setBuildings(null)
    setFloors(null)
    setSpaces(null)
    setMessage(null)
    setReloadKey((value) => value + 1)
  }

  const openSpace = spaces?.find((space) => space.id === openSpaceId) ?? null
  const floorChoices = (floors ?? []).filter((floor) =>
    selectedBuilding
      ? floor.building_id === selectedBuilding
      : floor.building_id === null,
  )

  async function handleBuilding(values: NameValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await createBuilding(workspaceId, {
        property_id: property.id,
        name: values.name.trim(),
      })
      refresh()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  async function handleFloor(values: FloorValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await createFloor(workspaceId, {
        property_id: property.id,
        name: values.name.trim(),
        ...(values.building_id ? { building_id: values.building_id } : {}),
      })
      refresh()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  async function handleSpace(values: SpaceValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      const created = await createSpace(workspaceId, {
        property_id: property.id,
        name: values.name.trim(),
        kind: values.kind,
        ...(values.building_id ? { building_id: values.building_id } : {}),
        ...(values.floor_id ? { floor_id: values.floor_id } : {}),
      })
      spaceForm.resetFields()
      setOpenSpaceId(created.kind === 'room' ? created.id : null)
      notifyCatalogChanged()
      refresh()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  async function handleAvailability(space: SpaceRecord, value: string) {
    setActionMessage(null)
    try {
      const updated = await updateSpaceAvailability(
        workspaceId,
        space.id,
        availabilityChoice(value),
      )
      setSpaces(
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)) ??
          null,
      )
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  async function handleDeleteSpace(spaceId: string) {
    setActionMessage(null)
    try {
      await deleteSpace(workspaceId, spaceId)
      setOpenSpaceId(null)
      refresh()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  async function handleDeleteProperty() {
    setActionMessage(null)
    try {
      await deleteProperty(workspaceId, property.id)
      onDeleted()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  return (
    <div style={{ maxWidth: '100%' }}>
      <Button onClick={onBack} style={{ marginBottom: 12 }}>
        All properties
      </Button>
      <Typography.Title level={3} style={{ marginTop: 0, fontSize: '1.2rem' }}>
        {property.name}
      </Typography.Title>
      <Typography.Paragraph>
        {property.address
          ? property.address
          : 'No address recorded. Buildings and floors are optional.'}
      </Typography.Paragraph>
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The property change was not saved"
          description={actionMessage}
        />
      ) : null}
      {message ? (
        <Alert
          type="error"
          showIcon
          title="Rooms could not be loaded"
          description={message}
          action={
            <Button size="small" onClick={refresh}>
              Try again
            </Button>
          }
        />
      ) : null}
      {spaces === null && !message ? (
        <Typography.Paragraph>Loading rooms…</Typography.Paragraph>
      ) : null}
      {spaces && openSpace ? (
        <RoomDetail
          workspaceId={workspaceId}
          space={openSpace}
          canManage={canManage}
          onBack={() => {
            setOpenSpaceId(null)
          }}
          onChange={(updated) => {
            setSpaces(
              (current) =>
                current?.map((item) =>
                  item.id === updated.id ? updated : item,
                ) ?? null,
            )
          }}
        />
      ) : null}
      {spaces && !openSpace ? (
        <>
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Buildings
          </Typography.Title>
          {buildings && buildings.length === 0 ? (
            <Typography.Paragraph>
              No buildings. A room or whole unit can sit directly on the
              property.
            </Typography.Paragraph>
          ) : null}
          {buildings && buildings.length > 0 ? (
            <ul style={{ paddingInlineStart: 18 }}>
              {buildings.map((building) => (
                <li key={building.id}>{building.name}</li>
              ))}
            </ul>
          ) : null}
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Floors
          </Typography.Title>
          {floors && floors.length === 0 ? (
            <Typography.Paragraph>No floors.</Typography.Paragraph>
          ) : null}
          {floors && floors.length > 0 ? (
            <ul style={{ paddingInlineStart: 18 }}>
              {floors.map((floor) => (
                <li key={floor.id}>{floor.name}</li>
              ))}
            </ul>
          ) : null}
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Rooms and whole units
          </Typography.Title>
          {spaces.length === 0 ? (
            <Typography.Paragraph>
              No rooms or whole units yet. A whole unit does not need a bed.
            </Typography.Paragraph>
          ) : (
            <ul style={{ paddingInlineStart: 0, listStyle: 'none' }}>
              {spaces.map((space) => (
                <li key={space.id} style={{ marginBottom: 12 }}>
                  <Button
                    onClick={() => {
                      setOpenSpaceId(space.id)
                    }}
                    style={{
                      width: '100%',
                      height: 'auto',
                      whiteSpace: 'normal',
                      textAlign: 'left',
                    }}
                  >
                    {space.name} · {kindLabel(space.kind)}
                  </Button>
                  {canManage ? (
                    <StatusSelect
                      label={`Availability for ${space.name}`}
                      record={space}
                      onChange={(value) => {
                        void handleAvailability(space, value)
                      }}
                    />
                  ) : (
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      {AVAILABILITY_OPTIONS.find(
                        (option) => option.value === availabilityValue(space),
                      )?.label ?? 'Active'}
                    </Typography.Paragraph>
                  )}
                  {space.kind === 'unit' ? (
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      Beds are not required for a whole unit.
                    </Typography.Paragraph>
                  ) : null}
                  {canManage ? (
                    <Popconfirm
                      title={`Remove ${space.name}?`}
                      okText="Remove"
                      cancelText="Cancel"
                      onConfirm={() => {
                        void handleDeleteSpace(space.id)
                      }}
                    >
                      <Button danger size="small" style={{ marginTop: 8 }}>
                        Remove {space.name}
                      </Button>
                    </Popconfirm>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {canManage ? (
            <>
              <Form<NameValues>
                layout="vertical"
                requiredMark={false}
                onFinish={(values) => {
                  void handleBuilding(values)
                }}
              >
                <Form.Item
                  label="Building name"
                  name="name"
                  rules={[{ required: true, message: 'Enter a building name.' }]}
                >
                  <Input />
                </Form.Item>
                <Button htmlType="submit" loading={saving}>
                  Add building
                </Button>
              </Form>
              <Form<FloorValues>
                layout="vertical"
                requiredMark={false}
                style={{ marginTop: 16 }}
                onFinish={(values) => {
                  void handleFloor(values)
                }}
              >
                <Form.Item
                  label="Floor name"
                  name="name"
                  rules={[{ required: true, message: 'Enter a floor name.' }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item label="Building for this floor" name="building_id">
                  <Select
                    allowClear
                    placeholder="No building"
                    options={(buildings ?? []).map((building) => ({
                      value: building.id,
                      label: building.name,
                    }))}
                  />
                </Form.Item>
                <Button htmlType="submit" loading={saving}>
                  Add floor
                </Button>
              </Form>
              <Form<SpaceValues>
                form={spaceForm}
                layout="vertical"
                requiredMark={false}
                style={{ marginTop: 16 }}
                initialValues={{ kind: 'room' }}
                onFinish={(values) => {
                  void handleSpace(values)
                }}
              >
                <Form.Item
                  label="Room or unit name"
                  name="name"
                  rules={[{ required: true, message: 'Enter a name.' }]}
                >
                  <Input />
                </Form.Item>
                <Form.Item
                  label="Kind"
                  name="kind"
                  rules={[{ required: true, message: 'Choose a kind.' }]}
                >
                  <Select options={KIND_OPTIONS} />
                </Form.Item>
                <Form.Item label="Building" name="building_id">
                  <Select
                    allowClear
                    placeholder="No building"
                    options={(buildings ?? []).map((building) => ({
                      value: building.id,
                      label: building.name,
                    }))}
                  />
                </Form.Item>
                <Form.Item label="Floor" name="floor_id">
                  <Select
                    allowClear
                    placeholder="No floor"
                    options={floorChoices.map((floor) => ({
                      value: floor.id,
                      label: floor.name,
                    }))}
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={saving}>
                  Add room or unit
                </Button>
              </Form>
            </>
          ) : null}
        </>
      ) : null}
      {canManage && !openSpace ? (
        <Popconfirm
          title={`Remove ${property.name} and its rooms?`}
          okText="Remove"
          cancelText="Cancel"
          onConfirm={() => {
            void handleDeleteProperty()
          }}
        >
          <Button danger style={{ marginTop: 16 }}>
            Remove property
          </Button>
        </Popconfirm>
      ) : null}
    </div>
  )
}

function RoomDetail({
  workspaceId,
  space,
  canManage,
  onBack,
  onChange,
}: {
  workspaceId: string
  space: SpaceRecord
  canManage: boolean
  onBack: () => void
  onChange: (space: SpaceRecord) => void
}) {
  const [beds, setBeds] = useState<BedRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [bedFormKey, setBedFormKey] = useState(0)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (space.kind !== 'room') {
      return
    }
    const controller = new AbortController()
    listBeds(workspaceId, space.id, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) {
          setBeds(rows)
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setMessage(errorText(error))
      })
    return () => {
      controller.abort()
    }
  }, [reloadKey, space.id, space.kind, workspaceId])

  async function handleBed(values: NameValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await createBed(workspaceId, { space_id: space.id, name: values.name.trim() })
      notifyCatalogChanged()
      setBeds(null)
      setMessage(null)
      setBedFormKey((value) => value + 1)
      setReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  async function handleBedAvailability(bed: BedRecord, value: string) {
    setActionMessage(null)
    try {
      const updated = await updateBedAvailability(
        workspaceId,
        bed.id,
        availabilityChoice(value),
      )
      setBeds(
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)) ??
          null,
      )
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  async function handleDeleteBed(bedId: string) {
    setActionMessage(null)
    try {
      await deleteBed(workspaceId, bedId)
      setBeds(null)
      setMessage(null)
      setReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  return (
    <div>
      <Button onClick={onBack} style={{ marginBottom: 12 }}>
        Back to property
      </Button>
      <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
        {space.name}
      </Typography.Title>
      <Typography.Paragraph>{kindLabel(space.kind)}</Typography.Paragraph>
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The room change was not saved"
          description={actionMessage}
        />
      ) : null}
      {space.kind === 'unit' ? (
        <Typography.Paragraph>
          This is a whole unit. Beds are not used here.
        </Typography.Paragraph>
      ) : (
        <>
          {message ? (
            <Alert
              type="error"
              showIcon
              title="Beds could not be loaded"
              description={message}
              action={
                <Button
                  size="small"
                  onClick={() => {
                    setMessage(null)
                    setBeds(null)
                    setReloadKey((value) => value + 1)
                  }}
                >
                  Try again
                </Button>
              }
            />
          ) : null}
          {beds === null && !message ? (
            <Typography.Paragraph>Loading beds…</Typography.Paragraph>
          ) : null}
          {beds && beds.length === 0 ? (
            <Typography.Paragraph>
              This room has no beds. Beds are optional.
            </Typography.Paragraph>
          ) : null}
          {beds && beds.length > 0 ? (
            <ul style={{ paddingInlineStart: 18 }}>
              {beds.map((bed) => (
                <li key={bed.id} style={{ marginBottom: 12 }}>
                  <span>{bed.name}</span>
                  {canManage ? (
                    <StatusSelect
                      label={`Availability for ${bed.name}`}
                      record={bed}
                      onChange={(value) => {
                        void handleBedAvailability(bed, value)
                      }}
                    />
                  ) : (
                    <Typography.Paragraph>
                      {AVAILABILITY_OPTIONS.find(
                        (option) => option.value === availabilityValue(bed),
                      )?.label ?? 'Active'}
                    </Typography.Paragraph>
                  )}
                  {canManage ? (
                    <Popconfirm
                      title={`Remove ${bed.name}?`}
                      okText="Remove"
                      cancelText="Cancel"
                      onConfirm={() => {
                        void handleDeleteBed(bed.id)
                      }}
                    >
                      <Button danger size="small" style={{ marginTop: 8 }}>
                        Remove {bed.name}
                      </Button>
                    </Popconfirm>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {canManage ? (
            <Form<NameValues>
              key={bedFormKey}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => {
                void handleBed(values)
              }}
            >
              <Form.Item
                label="Bed name"
                name="name"
                rules={[{ required: true, message: 'Enter a bed name.' }]}
              >
                <Input />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>
                Add bed
              </Button>
            </Form>
          ) : null}
        </>
      )}
      {canManage ? (
        <div style={{ marginTop: 16 }}>
          <StatusSelect
            label={`Availability for ${space.name}`}
            record={space}
            onChange={(value) => {
              void updateSpaceAvailability(
                workspaceId,
                space.id,
                availabilityChoice(value),
              )
                .then(onChange)
                .catch((error: unknown) => {
                  setActionMessage(errorText(error))
                })
            }}
          />
        </div>
      ) : null}
    </div>
  )
}

export function PropertiesScreen({
  workspaceId,
  role,
}: {
  workspaceId: string
  role: string
}) {
  const canView = role !== 'resident'
  const canManage = role === 'owner' || role === 'property_manager'
  const [properties, setProperties] = useState<PropertyRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [openId, setOpenId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!canView) {
      return
    }
    const controller = new AbortController()
    listProperties(workspaceId, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) {
          setProperties(rows)
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setMessage(errorText(error))
      })
    return () => {
      controller.abort()
    }
  }, [canView, reloadKey, workspaceId])

  if (!canView) {
    return (
      <section style={{ marginBottom: 24, maxWidth: '100%' }}>
        <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
          Properties
        </Typography.Title>
        <Alert
          type="info"
          showIcon
          title="Properties are limited to staff"
          description="Residents cannot view or manage properties, rooms, or beds."
        />
      </section>
    )
  }

  const open = properties?.find((property) => property.id === openId) ?? null

  async function handleCreate(values: PropertyValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      const created = await createProperty(workspaceId, {
        name: values.name.trim(),
        address: values.address?.trim() ?? '',
      })
      setOpenId(created.id)
      setCreating(false)
      setProperties(null)
      setMessage(null)
      notifyCatalogChanged()
      setReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section style={{ marginBottom: 24, maxWidth: '100%', overflowWrap: 'anywhere' }}>
      <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
        Properties
      </Typography.Title>
      {canManage ? (
        <Typography.Paragraph>
          Record each property, then add rooms or whole units. Beds belong only
          to rooms.
        </Typography.Paragraph>
      ) : (
        <Typography.Paragraph>
          You can view properties. Owners and property managers make changes.
        </Typography.Paragraph>
      )}
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The property was not saved"
          description={actionMessage}
        />
      ) : null}
      {message ? (
        <Alert
          type="error"
          showIcon
          title="Properties could not be loaded"
          description={message}
          action={
            <Button
              size="small"
              onClick={() => {
                setMessage(null)
                setProperties(null)
                setReloadKey((value) => value + 1)
              }}
            >
              Try again
            </Button>
          }
        />
      ) : null}
      {properties === null && !message ? (
        <Typography.Paragraph>Loading properties…</Typography.Paragraph>
      ) : null}
      {properties && open ? (
        <PropertyDetail
          key={open.id}
          workspaceId={workspaceId}
          property={open}
          canManage={canManage}
          onBack={() => {
            setOpenId(null)
          }}
          onDeleted={() => {
            setOpenId(null)
            setProperties(null)
            setMessage(null)
            setReloadKey((value) => value + 1)
          }}
        />
      ) : null}
      {properties && !open && properties.length === 0 ? (
        <Empty description="No properties yet. Add a property when you are ready to record its rooms or whole units. Buildings and floors are optional, and a whole unit does not need a bed." />
      ) : null}
      {properties && !open && properties.length > 0 ? (
        <Table
          rowKey="id"
          pagination={false}
          dataSource={properties}
          style={{ marginBottom: 16 }}
          columns={[
            { title: 'Property', dataIndex: 'name' },
            {
              title: 'Address',
              dataIndex: 'address',
              render: (value: string) => value || 'No address recorded',
            },
            {
              title: '',
              key: 'open',
              render: (_value, property) => (
                <Button
                  type="link"
                  onClick={() => {
                    setOpenId(property.id)
                  }}
                >
                  Open {property.name}
                </Button>
              ),
            },
          ]}
        />
      ) : null}
      {canManage && !open ? (
        <>
          <Button
            type="primary"
            onClick={() => {
              setCreating(true)
            }}
          >
            New property
          </Button>
          <Modal
            title="Add a property"
            open={creating}
            onCancel={() => {
              setCreating(false)
            }}
            footer={null}
            destroyOnHidden
          >
            <Form<PropertyValues>
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => {
                void handleCreate(values)
              }}
            >
              <Form.Item
                label="Property name"
                name="name"
                rules={[{ required: true, message: 'Enter a property name.' }]}
              >
                <Input />
              </Form.Item>
              <Form.Item label="Address" name="address">
                <Input />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>
                Add property
              </Button>
            </Form>
          </Modal>
        </>
      ) : null}
    </section>
  )
}
