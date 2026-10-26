import {
  Alert,
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useEffect, useState } from 'react'
import { notifyCatalogChanged, useCatalogRevision } from './catalog'
import {
  listBeds,
  listProperties,
  listSpaces,
  type BedRecord,
  type SpaceRecord,
} from './api/properties'
import {
  cancelAssignment,
  cancelBooking,
  cancelTenancy,
  checkInAssignment,
  checkOutAssignment,
  convertBooking,
  createBooking,
  createResident,
  createTenancy,
  endTenancy,
  listAssignments,
  listAvailability,
  listBookings,
  listResidents,
  listTenancies,
  transferAssignment,
  updateAssignment,
  updateOwnContact,
  updateResident,
  type AssignmentRecord,
  type AvailabilityRow,
  type BookingRecord,
  type ResidentRecord,
  type TenancyRecord,
} from './api/occupancy'
import { errorText } from './api/session'
import { formatMoney } from './money'

const SECTIONS = [
  { id: 'residents', label: 'Residents' },
  { id: 'bookings', label: 'Bookings' },
  { id: 'tenancies', label: 'Tenancies' },
  { id: 'stays', label: 'Stays' },
  { id: 'availability', label: 'Availability' },
] as const

type SectionId = (typeof SECTIONS)[number]['id']

const FEE_PERIODS = [
  { value: 'night', label: 'Night' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
]

const STATE_LABELS: Record<string, string> = {
  free: 'Free',
  occupied: 'Occupied',
  unavailable: 'Unavailable',
  partly_occupied: 'Not free to book as a whole',
}

function canManage(role: string): boolean {
  return role === 'owner' || role === 'property_manager'
}

function stayDates(start: string, end: string | null): string {
  return end === null ? `${start}, open ended` : `${start} to ${end}`
}

function placeLabel(space: SpaceRecord, beds: BedRecord[]): string {
  const bedNames = beds
    .filter((bed) => bed.space_id === space.id)
    .map((bed) => bed.name)
  const bedsLabel = bedNames.length > 0 ? ` (${bedNames.join(', ')})` : ''
  const kind = space.kind === 'unit' ? 'Whole unit' : 'Room'
  return `${space.name} · ${kind}${bedsLabel}`
}

type ResidentValues = {
  first_name: string
  last_name: string
  email?: string
  phone?: string
  account_email?: string
}

type StayValues = {
  resident_id: string
  space_id: string
  bed_id?: string
  start_date: string
  end_date?: string
  fee_amount?: string
  fee_period?: string
  deposit_amount?: string
}

function usePlaces(workspaceId: string, enabled: boolean) {
  const [spaces, setSpaces] = useState<SpaceRecord[] | null>(null)
  const [beds, setBeds] = useState<BedRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const revision = useCatalogRevision()

  useEffect(() => {
    if (!enabled) {
      return
    }
    const controller = new AbortController()
    let active = true
    listProperties(workspaceId, controller.signal)
      .then(async (properties) => {
        const spaceGroups = await Promise.all(
          properties.map((property) =>
            listSpaces(workspaceId, property.id, controller.signal),
          ),
        )
        const nextSpaces = spaceGroups.flat()
        if (!active) {
          return
        }
        setSpaces(nextSpaces)
        const bedGroups = await Promise.all(
          nextSpaces
            .filter((space) => space.kind === 'room')
            .map((space) => listBeds(workspaceId, space.id, controller.signal)),
        )
        if (!active) {
          return
        }
        setBeds(bedGroups.flat())
      })
      .catch((error: unknown) => {
        if (active && !controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [workspaceId, enabled, revision])

  return { spaces, beds, message }
}

function OwnContactForm({
  workspaceId,
  resident,
  onSaved,
}: {
  workspaceId: string
  resident: ResidentRecord
  onSaved: (resident: ResidentRecord) => void
}) {
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  return (
    <Form<{ phone?: string; email?: string }>
      layout="vertical"
      requiredMark={false}
      initialValues={{ phone: resident.phone, email: resident.email }}
      onFinish={async (values) => {
        setSaving(true)
        setMessage(null)
        try {
          onSaved(
            await updateOwnContact(workspaceId, resident.id, {
              phone: values.phone?.trim() ?? '',
              email: values.email?.trim() ?? '',
            }),
          )
        } catch (error: unknown) {
          setMessage(errorText(error))
        } finally {
          setSaving(false)
        }
      }}
    >
      {message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="Your contact details were not saved"
          description={message}
        />
      ) : null}
      <Form.Item label="Phone" name="phone">
        <Input autoComplete="tel" inputMode="tel" />
      </Form.Item>
      <Form.Item label="Email" name="email">
        <Input type="email" autoComplete="email" inputMode="email" />
      </Form.Item>
      <Button htmlType="submit" loading={saving}>
        Save contact details
      </Button>
    </Form>
  )
}

function ResidentStay({ workspaceId }: { workspaceId: string }) {
  const [residents, setResidents] = useState<ResidentRecord[] | null>(null)
  const [tenancies, setTenancies] = useState<TenancyRecord[] | null>(null)
  const [stays, setStays] = useState<AssignmentRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      listResidents(workspaceId, controller.signal),
      listTenancies(workspaceId, controller.signal),
      listAssignments(workspaceId, controller.signal),
    ])
      .then(([nextResidents, nextTenancies, nextStays]) => {
        if (!controller.signal.aborted) {
          setResidents(nextResidents)
          setTenancies(nextTenancies)
          setStays(nextStays)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId])

  return (
    <section>
      <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
        Your stay
      </Typography.Title>
      <Typography.Paragraph>
        You can see your own profile and tenancy, and you can update your phone
        and email. The owner keeps your name.
      </Typography.Paragraph>
      {message ? (
        <Alert
          type="error"
          showIcon
          title="Your stay could not be loaded"
          description={message}
        />
      ) : null}
      {residents === null && !message ? (
        <Typography.Paragraph>Loading your stay…</Typography.Paragraph>
      ) : null}
      {residents && residents.length === 0 ? (
        <Typography.Paragraph>
          No stay is recorded for you yet. The owner adds your profile and
          tenancy.
        </Typography.Paragraph>
      ) : null}
      {residents?.map((resident) => (
        <div key={resident.id}>
          <Typography.Paragraph>
            {resident.first_name} {resident.last_name}
            {resident.phone ? ` · ${resident.phone}` : ''}
            {resident.email ? ` · ${resident.email}` : ''}
          </Typography.Paragraph>
          <OwnContactForm
            workspaceId={workspaceId}
            resident={resident}
            onSaved={(next) => {
              setResidents((current) =>
                current?.map((row) => (row.id === next.id ? next : row)) ?? [next],
              )
            }}
          />
        </div>
      ))}
      {tenancies?.map((tenancy) => (
        <Typography.Paragraph key={tenancy.id}>
          Agreement {tenancy.status}. {stayDates(tenancy.start_date, tenancy.end_date)}.
          Fee {formatMoney(tenancy.fee_amount, tenancy.currency_code)} per {tenancy.fee_period}.
          Deposit {formatMoney(tenancy.deposit_amount, tenancy.currency_code)}.
        </Typography.Paragraph>
      ))}
      {stays?.map((stay) => (
        <Typography.Paragraph key={stay.id}>
          {stay.space_name}
          {stay.bed_name ? ` · ${stay.bed_name}` : ''} · {stay.status}.{' '}
          {stayDates(stay.start_date, stay.end_date)}.
        </Typography.Paragraph>
      ))}
    </section>
  )
}

export function OccupancyScreen({
  workspaceId,
  role,
  initialSection = 'residents',
  showSections = true,
  heading = 'Residents and stays',
}: {
  workspaceId: string
  role: string
  initialSection?: SectionId
  showSections?: boolean
  heading?: string
}) {
  const [section, setSection] = useState<SectionId>(initialSection)
  const [reloadKey, setReloadKey] = useState(0)
  const manage = canManage(role)

  if (role === 'resident') {
    return <ResidentStay workspaceId={workspaceId} />
  }

  return (
    <section>
      <Typography.Title level={2} style={{ marginTop: 0 }}>
        {heading}
      </Typography.Title>
      <Typography.Paragraph>
        The end date is the last occupied day. The space is free the next day.
        A confirmed or active stay blocks that unit, room, or bed.
      </Typography.Paragraph>
      {!manage ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          title="View only"
          description="You can view residents and stays. An owner or property manager records them."
        />
      ) : null}
      {showSections ? (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        {SECTIONS.map((item) => (
          <Button
            key={item.id}
            type={section === item.id ? 'primary' : 'default'}
            onClick={() => {
              setSection(item.id)
            }}
          >
            {item.label}
          </Button>
        ))}
      </div>
      ) : null}
      {section === 'residents' ? (
        <ResidentsPanel
          workspaceId={workspaceId}
          manage={manage}
          reloadKey={reloadKey}
          onChanged={() => {
            setReloadKey((value) => value + 1)
          }}
        />
      ) : null}
      {section === 'bookings' ? (
        <BookingsPanel
          workspaceId={workspaceId}
          manage={manage}
          reloadKey={reloadKey}
          onChanged={() => {
            setReloadKey((value) => value + 1)
          }}
        />
      ) : null}
      {section === 'tenancies' ? (
        <TenanciesPanel
          workspaceId={workspaceId}
          manage={manage}
          reloadKey={reloadKey}
          onChanged={() => {
            setReloadKey((value) => value + 1)
          }}
        />
      ) : null}
      {section === 'stays' ? (
        <StaysPanel
          workspaceId={workspaceId}
          manage={manage}
          reloadKey={reloadKey}
          onChanged={() => {
            setReloadKey((value) => value + 1)
          }}
        />
      ) : null}
      {section === 'availability' ? (
        <AvailabilityPanel workspaceId={workspaceId} />
      ) : null}
    </section>
  )
}

function ResidentsPanel({
  workspaceId,
  manage,
  reloadKey,
  onChanged,
}: {
  workspaceId: string
  manage: boolean
  reloadKey: number
  onChanged: () => void
}) {
  const [rows, setRows] = useState<ResidentRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    listResidents(workspaceId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) {
          setRows(next)
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setRows(null)
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, reloadKey])

  async function handleCreate(values: ResidentValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await createResident(workspaceId, {
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        email: values.email?.trim() ?? '',
        phone: values.phone?.trim() ?? '',
        account_email: values.account_email?.trim() ?? '',
      })
      notifyCatalogChanged()
      setAdding(false)
      onChanged()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="Residents could not be loaded"
          description={message}
        />
      ) : null}
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The resident was not saved"
          description={actionMessage}
        />
      ) : null}
      {rows === null && !message ? (
        <Typography.Paragraph>Loading residents…</Typography.Paragraph>
      ) : null}
      {rows && rows.length === 0 ? (
        <Empty description="No residents yet. Add the person before recording a stay." />
      ) : null}
      {rows && rows.length > 0 ? (
        <Table
          rowKey="id"
          pagination={false}
          dataSource={rows}
          expandable={
            manage
              ? {
                  expandedRowRender: (resident) => (
                    <ResidentEditor
                      workspaceId={workspaceId}
                      resident={resident}
                      onChanged={onChanged}
                      onError={setActionMessage}
                    />
                  ),
                }
              : undefined
          }
          columns={[
            {
              title: 'Name',
              key: 'name',
              render: (_value, resident) => `${resident.first_name} ${resident.last_name}`,
            },
            { title: 'Phone', dataIndex: 'phone', render: (value: string) => value || '—' },
            { title: 'Email', dataIndex: 'email', render: (value: string) => value || '—' },
          ]}
        />
      ) : null}
      {manage ? (
        <>
        <Button
          type="primary"
          style={{ marginTop: 16 }}
          onClick={() => {
            setAdding(true)
          }}
        >
          Add resident
        </Button>
        <Modal
          title="Add a resident"
          open={adding}
          onCancel={() => {
            setAdding(false)
          }}
          footer={null}
          destroyOnHidden
        >
        <Form<ResidentValues>
          key={reloadKey}
          layout="vertical"
          requiredMark={false}
          onFinish={(values) => {
            void handleCreate(values)
          }}
        >
          <Form.Item
            label="First name"
            name="first_name"
            rules={[{ required: true, message: 'Enter a first name.' }]}
          >
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item
            label="Last name"
            name="last_name"
            rules={[{ required: true, message: 'Enter a last name.' }]}
          >
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item label="Phone" name="phone">
            <Input autoComplete="off" inputMode="tel" />
          </Form.Item>
          <Form.Item label="Contact email" name="email">
            <Input type="email" autoComplete="off" inputMode="email" />
          </Form.Item>
          <Form.Item
            label="Sign-in email"
            name="account_email"
            extra="Optional. Use it only when this person already has a resident membership."
          >
            <Input type="email" autoComplete="off" inputMode="email" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            Add resident
          </Button>
        </Form>
        </Modal>
        </>
      ) : null}
    </>
  )
}

function ResidentEditor({
  workspaceId,
  resident,
  onChanged,
  onError,
}: {
  workspaceId: string
  resident: ResidentRecord
  onChanged: () => void
  onError: (message: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  async function handleSave(values: ResidentValues) {
    setSaving(true)
    onError(null)
    try {
      await updateResident(workspaceId, resident.id, {
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        email: values.email?.trim() ?? '',
        phone: values.phone?.trim() ?? '',
        account_email: values.account_email?.trim() ?? '',
      })
      setOpen(false)
      onChanged()
    } catch (error: unknown) {
      onError(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <Button
        size="small"
        style={{ marginInlineStart: 8 }}
        onClick={() => {
          setOpen(true)
        }}
      >
        Edit {resident.first_name} {resident.last_name}
      </Button>
    )
  }

  return (
    <Form<ResidentValues>
      layout="vertical"
      requiredMark={false}
      style={{ marginTop: 8 }}
      initialValues={{
        first_name: resident.first_name,
        last_name: resident.last_name,
        phone: resident.phone,
        email: resident.email,
        account_email: resident.account_email,
      }}
      onFinish={(values) => {
        void handleSave(values)
      }}
    >
      <Form.Item
        label="First name"
        name="first_name"
        rules={[{ required: true, message: 'Enter a first name.' }]}
      >
        <Input autoComplete="off" />
      </Form.Item>
      <Form.Item
        label="Last name"
        name="last_name"
        rules={[{ required: true, message: 'Enter a last name.' }]}
      >
        <Input autoComplete="off" />
      </Form.Item>
      <Form.Item label="Phone" name="phone">
        <Input autoComplete="off" inputMode="tel" />
      </Form.Item>
      <Form.Item label="Contact email" name="email">
        <Input type="email" autoComplete="off" inputMode="email" />
      </Form.Item>
      <Form.Item label="Sign-in email" name="account_email">
        <Input type="email" autoComplete="off" inputMode="email" />
      </Form.Item>
      <Button type="primary" htmlType="submit" loading={saving}>
        Save {resident.first_name} {resident.last_name}
      </Button>
    </Form>
  )
}

function BookingsPanel({
  workspaceId,
  manage,
  reloadKey,
  onChanged,
}: {
  workspaceId: string
  manage: boolean
  reloadKey: number
  onChanged: () => void
}) {
  const [rows, setRows] = useState<BookingRecord[] | null>(null)
  const [residents, setResidents] = useState<ResidentRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const places = usePlaces(workspaceId, true)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      listBookings(workspaceId, controller.signal),
      listResidents(workspaceId, controller.signal),
    ])
      .then(([nextRows, nextResidents]) => {
        if (!controller.signal.aborted) {
          setRows(nextRows)
          setResidents(nextResidents)
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, reloadKey])

  async function handleCreate(values: StayValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await createBooking(workspaceId, {
        resident_id: values.resident_id,
        space_id: values.space_id,
        bed_id: values.bed_id || null,
        start_date: values.start_date,
        end_date: values.end_date || null,
      })
      setCreating(false)
      onChanged()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  async function handleCancel(bookingId: string) {
    setActionMessage(null)
    try {
      await cancelBooking(workspaceId, bookingId)
      onChanged()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  async function handleConvert(bookingId: string, values: StayValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await convertBooking(workspaceId, bookingId, {
        fee_amount: values.fee_amount ?? '',
        fee_period: values.fee_period ?? 'month',
        deposit_amount: values.deposit_amount || '0',
        check_in: false,
      })
      onChanged()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  const spaces = places.spaces ?? []
  const beds = places.beds ?? []

  return (
    <>
      {message || places.message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="Bookings could not be loaded"
          description={message ?? places.message}
        />
      ) : null}
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The reservation was not saved"
          description={actionMessage}
        />
      ) : null}
      {rows === null && !message ? (
        <Typography.Paragraph>Loading bookings…</Typography.Paragraph>
      ) : null}
      {rows && rows.length === 0 ? (
        <Typography.Paragraph>No reservations yet.</Typography.Paragraph>
      ) : null}
      {rows?.map((booking) => (
        <div key={booking.id} style={{ marginBottom: 16 }}>
          <Typography.Paragraph style={{ marginBottom: 8 }}>
            <span>
              {booking.resident_name} · {booking.status}.
            </span>{' '}
            <Tag>{booking.status}</Tag>{' '}
            {stayDates(booking.start_date, booking.end_date)}
            {booking.space_id
              ? ` · ${spaces.find((space) => space.id === booking.space_id)?.name ?? 'Space'}`
              : ''}
            {booking.bed_id
              ? ` · ${beds.find((bed) => bed.id === booking.bed_id)?.name ?? 'Bed'}`
              : ''}
            .
          </Typography.Paragraph>
          {manage && booking.status === 'confirmed' ? (
            <>
              <Popconfirm
                title="Cancel this reservation?"
                okText="Cancel reservation"
                cancelText="Keep"
                onConfirm={() => {
                  void handleCancel(booking.id)
                }}
              >
                <Button size="small">Cancel reservation</Button>
              </Popconfirm>
              <Form<StayValues>
                layout="vertical"
                requiredMark={false}
                style={{ marginTop: 8 }}
                initialValues={{ fee_period: 'month' }}
                onFinish={(values) => {
                  void handleConvert(booking.id, values)
                }}
              >
                <Form.Item
                  label="Agreed fee"
                  name="fee_amount"
                  rules={[{ required: true, message: 'Enter the agreed fee.' }]}
                >
                  <Input inputMode="decimal" autoComplete="off" />
                </Form.Item>
                <Form.Item label="Fee period" name="fee_period">
                  <Select options={FEE_PERIODS} />
                </Form.Item>
                <Form.Item label="Deposit" name="deposit_amount">
                  <Input inputMode="decimal" autoComplete="off" placeholder="0.00" />
                </Form.Item>
                <Button htmlType="submit" loading={saving}>
                  Convert to tenancy
                </Button>
              </Form>
            </>
          ) : null}
        </div>
      ))}
      {manage ? (
        <>
          <Button
            type="primary"
            onClick={() => {
              setCreating(true)
            }}
          >
            New reservation
          </Button>
          <Drawer
            title="New reservation"
            open={creating}
            onClose={() => {
              setCreating(false)
            }}
            size="large"
            destroyOnHidden
          >
            <Form<StayValues>
              key={reloadKey}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => {
                void handleCreate(values)
              }}
            >
              <TargetFields residents={residents} spaces={spaces} beds={beds} />
              <Button type="primary" htmlType="submit" loading={saving}>
                Add reservation
              </Button>
            </Form>
          </Drawer>
        </>
      ) : null}
    </>
  )
}

function TargetFields({
  residents,
  spaces,
  beds,
}: {
  residents: ResidentRecord[]
  spaces: SpaceRecord[]
  beds: BedRecord[]
}) {
  const form = Form.useFormInstance<StayValues>()
  const [spaceId, setSpaceId] = useState<string | undefined>()
  const bedOptions = beds
    .filter((bed) => bed.space_id === spaceId)
    .map((bed) => ({ value: bed.id, label: bed.name }))

  return (
    <>
      <Form.Item
        label="Resident"
        name="resident_id"
        rules={[{ required: true, message: 'Choose a resident.' }]}
      >
        <Select
          options={residents.map((resident) => ({
            value: resident.id,
            label: `${resident.first_name} ${resident.last_name}`,
          }))}
        />
      </Form.Item>
      <Form.Item
        label="Space"
        name="space_id"
        rules={[{ required: true, message: 'Choose a space.' }]}
      >
        <Select
          options={spaces.map((space) => ({
            value: space.id,
            label: placeLabel(space, beds),
          }))}
          onChange={(value) => {
            if (typeof value === 'string') {
              setSpaceId(value)
              form.setFieldValue('bed_id', undefined)
            }
          }}
        />
      </Form.Item>
      <Form.Item label="Start date" name="start_date" rules={[{ required: true, message: 'Choose a start date.' }]}>
        <Input type="date" />
      </Form.Item>
      <Form.Item label="End date" name="end_date" extra="Last occupied day. Leave blank for an open-ended stay.">
        <Input type="date" />
      </Form.Item>
      {bedOptions.length > 0 ? (
        <Form.Item label="Bed" name="bed_id" extra="Leave blank to book the whole room.">
          <Select allowClear options={bedOptions} />
        </Form.Item>
      ) : null}
    </>
  )
}

function TenanciesPanel({
  workspaceId,
  manage,
  reloadKey,
  onChanged,
}: {
  workspaceId: string
  manage: boolean
  reloadKey: number
  onChanged: () => void
}) {
  const [rows, setRows] = useState<TenancyRecord[] | null>(null)
  const [residents, setResidents] = useState<ResidentRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const places = usePlaces(workspaceId, true)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      listTenancies(workspaceId, controller.signal),
      listResidents(workspaceId, controller.signal),
    ])
      .then(([nextRows, nextResidents]) => {
        if (!controller.signal.aborted) {
          setRows(nextRows)
          setResidents(nextResidents)
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, reloadKey])

  async function handleCreate(values: StayValues) {
    setSaving(true)
    setActionMessage(null)
    try {
      await createTenancy(workspaceId, {
        resident_id: values.resident_id,
        space_id: values.space_id,
        bed_id: values.bed_id || null,
        start_date: values.start_date,
        end_date: values.end_date || null,
        fee_amount: values.fee_amount ?? '',
        fee_period: values.fee_period ?? 'month',
        deposit_amount: values.deposit_amount || '0',
        check_in: false,
      })
      notifyCatalogChanged()
      onChanged()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {message || places.message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="Tenancies could not be loaded"
          description={message ?? places.message}
        />
      ) : null}
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The agreement was not saved"
          description={actionMessage}
        />
      ) : null}
      {rows === null && !message ? (
        <Typography.Paragraph>Loading tenancies…</Typography.Paragraph>
      ) : null}
      {rows && rows.length === 0 ? (
        <Typography.Paragraph>No tenancies yet.</Typography.Paragraph>
      ) : null}
      {rows?.map((tenancy) => (
        <div key={tenancy.id} style={{ marginBottom: 12 }}>
          <Typography.Paragraph style={{ marginBottom: 8 }}>
            {tenancy.resident_name} · {tenancy.status}.{' '}
            {stayDates(tenancy.start_date, tenancy.end_date)}. Fee{' '}
            {formatMoney(tenancy.fee_amount, tenancy.currency_code)} per {tenancy.fee_period}.
            Deposit {formatMoney(tenancy.deposit_amount, tenancy.currency_code)}.
          </Typography.Paragraph>
          {manage && tenancy.status === 'active' ? (
            <TenancyActions
              workspaceId={workspaceId}
              tenancy={tenancy}
              onChanged={onChanged}
              onError={setActionMessage}
            />
          ) : null}
        </div>
      ))}
      {manage ? (
        <Form<StayValues>
          key={reloadKey}
          layout="vertical"
          requiredMark={false}
          initialValues={{ fee_period: 'month' }}
          onFinish={(values) => {
            void handleCreate(values)
          }}
        >
          <TargetFields
            residents={residents}
            spaces={places.spaces ?? []}
            beds={places.beds ?? []}
          />
          <Form.Item
            label="Agreed fee"
            name="fee_amount"
            rules={[{ required: true, message: 'Enter the agreed fee.' }]}
          >
            <Input inputMode="decimal" autoComplete="off" />
          </Form.Item>
          <Form.Item label="Fee period" name="fee_period">
            <Select options={FEE_PERIODS} />
          </Form.Item>
          <Form.Item label="Deposit" name="deposit_amount">
            <Input inputMode="decimal" autoComplete="off" placeholder="0.00" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            Add tenancy
          </Button>
        </Form>
      ) : null}
    </>
  )
}

function TenancyActions({
  workspaceId,
  tenancy,
  onChanged,
  onError,
}: {
  workspaceId: string
  tenancy: TenancyRecord
  onChanged: () => void
  onError: (message: string | null) => void
}) {
  const [endDate, setEndDate] = useState('')

  async function run(action: () => Promise<unknown>) {
    onError(null)
    try {
      await action()
      onChanged()
    } catch (error: unknown) {
      onError(errorText(error))
    }
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      <Input
        type="date"
        aria-label={`End date for ${tenancy.resident_name}`}
        value={endDate}
        onChange={(event) => {
          setEndDate(event.target.value)
        }}
        style={{ maxWidth: 220 }}
      />
      <Button
        disabled={!endDate}
        onClick={() => {
          void run(() => endTenancy(workspaceId, tenancy.id, endDate))
        }}
      >
        End agreement
      </Button>
      <Button
        onClick={() => {
          void run(() => cancelTenancy(workspaceId, tenancy.id))
        }}
      >
        Cancel agreement
      </Button>
    </div>
  )
}

function StaysPanel({
  workspaceId,
  manage,
  reloadKey,
  onChanged,
}: {
  workspaceId: string
  manage: boolean
  reloadKey: number
  onChanged: () => void
}) {
  const [rows, setRows] = useState<AssignmentRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const places = usePlaces(workspaceId, manage)

  useEffect(() => {
    const controller = new AbortController()
    listAssignments(workspaceId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) {
          setRows(next)
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, reloadKey])

  return (
    <>
      {message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="Stays could not be loaded"
          description={message}
        />
      ) : null}
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The stay was not saved"
          description={actionMessage}
        />
      ) : null}
      {rows === null && !message ? (
        <Typography.Paragraph>Loading stays…</Typography.Paragraph>
      ) : null}
      {rows && rows.length === 0 ? (
        <Typography.Paragraph>No stays yet.</Typography.Paragraph>
      ) : null}
      {rows?.map((stay) => (
        <div key={stay.id} style={{ marginBottom: 16 }}>
          <Typography.Paragraph style={{ marginBottom: 8 }}>
            {stay.resident_name} · {stay.space_name}
            {stay.bed_name ? ` · ${stay.bed_name}` : ''} · {stay.status}.{' '}
            {stayDates(stay.start_date, stay.end_date)}.
          </Typography.Paragraph>
          {manage && (stay.status === 'confirmed' || stay.status === 'active') ? (
            <StayActions
              key={`${stay.id}-${stay.status}-${stay.start_date}-${stay.end_date ?? 'open'}`}
              workspaceId={workspaceId}
              stay={stay}
              spaces={places.spaces ?? []}
              beds={places.beds ?? []}
              onChanged={onChanged}
              onError={setActionMessage}
            />
          ) : null}
        </div>
      ))}
    </>
  )
}

function StayActions({
  workspaceId,
  stay,
  spaces,
  beds,
  onChanged,
  onError,
}: {
  workspaceId: string
  stay: AssignmentRecord
  spaces: SpaceRecord[]
  beds: BedRecord[]
  onChanged: () => void
  onError: (message: string | null) => void
}) {
  const [endDate, setEndDate] = useState(stay.end_date ?? '')
  const [startDate, setStartDate] = useState(stay.start_date)
  const [plannedEnd, setPlannedEnd] = useState(stay.end_date ?? '')
  const [moveDate, setMoveDate] = useState('')
  const [moveSpace, setMoveSpace] = useState<string | undefined>()
  const [moveBed, setMoveBed] = useState<string | undefined>()
  const roomBeds = beds.filter((bed) => bed.space_id === moveSpace)

  async function run(action: () => Promise<unknown>) {
    onError(null)
    try {
      await action()
      onChanged()
    } catch (error: unknown) {
      onError(errorText(error))
    }
  }

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {stay.status === 'confirmed' ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Button
            size="small"
            onClick={() => {
              void run(() => checkInAssignment(workspaceId, stay.id))
            }}
          >
            Check in {stay.resident_name}
          </Button>
          <Button
            size="small"
            onClick={() => {
              void run(() => cancelAssignment(workspaceId, stay.id))
            }}
          >
            Cancel stay
          </Button>
        </div>
      ) : null}
      {stay.status === 'active' ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <Input
            type="date"
            aria-label={`Last occupied day for ${stay.resident_name}`}
            value={endDate}
            onChange={(event) => {
              setEndDate(event.target.value)
            }}
            style={{ maxWidth: 220 }}
          />
          <Button
            size="small"
            disabled={!endDate}
            onClick={() => {
              void run(() => checkOutAssignment(workspaceId, stay.id, endDate))
            }}
          >
            Check out {stay.resident_name}
          </Button>
        </div>
      ) : null}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Input
          type="date"
          aria-label={`Start date for ${stay.resident_name}`}
          value={startDate}
          onChange={(event) => {
            setStartDate(event.target.value)
          }}
          style={{ maxWidth: 180 }}
        />
        <Input
          type="date"
          aria-label={`Planned end for ${stay.resident_name}`}
          value={plannedEnd}
          onChange={(event) => {
            setPlannedEnd(event.target.value)
          }}
          style={{ maxWidth: 180 }}
        />
        <Button
          size="small"
          disabled={!startDate}
          onClick={() => {
            void run(() =>
              updateAssignment(workspaceId, stay.id, {
                start_date: startDate,
                end_date: plannedEnd || null,
              }),
            )
          }}
        >
          Update dates
        </Button>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Select
          aria-label={`Move ${stay.resident_name} to`}
          placeholder="Space"
          style={{ minWidth: 180 }}
          value={moveSpace}
          options={spaces.map((space) => ({
            value: space.id,
            label: space.name,
          }))}
          onChange={(value) => {
            if (typeof value === 'string') {
              setMoveSpace(value)
              setMoveBed(undefined)
            }
          }}
        />
        {roomBeds.length > 0 ? (
          <Select
            aria-label={`Bed for ${stay.resident_name}`}
            allowClear
            placeholder="Whole room"
            style={{ minWidth: 140 }}
            value={moveBed}
            options={roomBeds.map((bed) => ({ value: bed.id, label: bed.name }))}
            onChange={(value) => {
              setMoveBed(typeof value === 'string' ? value : undefined)
            }}
          />
        ) : null}
        <Input
          type="date"
          aria-label={`Move day for ${stay.resident_name}`}
          value={moveDate}
          onChange={(event) => {
            setMoveDate(event.target.value)
          }}
          style={{ maxWidth: 180 }}
        />
        <Button
          size="small"
          disabled={!moveSpace || !moveDate}
          onClick={() => {
            if (!moveSpace) {
              return
            }
            void run(() =>
              transferAssignment(workspaceId, stay.id, {
                space_id: moveSpace,
                bed_id: moveBed || null,
                start_date: moveDate,
              }),
            )
          }}
        >
          Transfer {stay.resident_name}
        </Button>
      </div>
    </div>
  )
}

function AvailabilityPanel({ workspaceId }: { workspaceId: string }) {
  const [on, setOn] = useState('')
  const [rows, setRows] = useState<AvailabilityRow[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load(date: string) {
    setLoading(true)
    setMessage(null)
    try {
      setRows(await listAvailability(workspaceId, date))
    } catch (error: unknown) {
      setRows(null)
      setMessage(errorText(error))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Form
        layout="vertical"
        requiredMark={false}
        onFinish={() => {
          void load(on)
        }}
      >
        <Form.Item label="Date" required>
          <Input
            type="date"
            aria-label="Availability date"
            value={on}
            onChange={(event) => {
              setOn(event.target.value)
            }}
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} disabled={!on}>
          Show availability
        </Button>
      </Form>
      {loading ? (
        <Typography.Paragraph style={{ marginTop: 16 }}>
          Checking availability…
        </Typography.Paragraph>
      ) : null}
      {message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginTop: 16 }}
          title="Availability could not be loaded"
          description={message}
        />
      ) : null}
      {rows && rows.length === 0 ? (
        <Typography.Paragraph style={{ marginTop: 16 }}>
          No spaces are recorded for this workspace.
        </Typography.Paragraph>
      ) : null}
      {rows && rows.length > 0 ? (
        <ul style={{ paddingInlineStart: 18, marginTop: 16 }}>
          {rows.map((row) => (
            <li key={`${row.space_id}-${row.bed_id ?? 'space'}`} style={{ marginBottom: 8 }}>
              {row.space_name}
              {row.bed_name ? ` · ${row.bed_name}` : ''} ·{' '}
              {STATE_LABELS[row.state] ?? row.state}
              {row.resident_name ? ` · ${row.resident_name}` : ''}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  )
}
