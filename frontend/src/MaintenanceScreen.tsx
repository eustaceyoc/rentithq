import { Alert, Button, Empty, Form, Input, Select, Table, Typography } from 'antd'
import { useEffect, useState } from 'react'
import {
  createMaintenanceRequest,
  listMaintenanceRequests,
  updateMaintenanceRequest,
  type MaintenanceRequestRecord,
} from './api/maintenance'
import { listAssignments, listResidents, type AssignmentRecord, type ResidentRecord } from './api/occupancy'
import { listBeds, listProperties, listSpaces, type BedRecord, type PropertyRecord, type SpaceRecord } from './api/properties'
import { errorText, listMembers, type Member } from './api/session'
import { useCatalogRevision } from './catalog'
import { formatMoney } from './money'
import { PageHeader } from './ui/PageHeader'
import { StatusTag } from './ui/StatusTag'

const PRIORITIES = [
  { value: 'low', label: 'Low' },
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
]

const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'assigned', label: 'Assigned' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

type FileValues = {
  property_id?: string
  space_id?: string
  bed_id?: string
  resident_id?: string
  assignee_id?: string
  place?: string
  description: string
  priority: string
}

type UpdateValues = {
  status?: string
  assignee_id?: string
  note?: string
  completion_note?: string
  cost_amount?: string
}

function placeLabel(request: MaintenanceRequestRecord): string {
  const parts = [request.property_name, request.space_name, request.bed_name].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : 'No place named'
}

export function MaintenanceScreen({
  workspaceId,
  role,
}: {
  workspaceId: string
  role: string
}) {
  const resident = role === 'resident'
  const triage = role === 'owner' || role === 'property_manager'
  const canUpdate = triage || role === 'maintenance'
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [message, setMessage] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [requests, setRequests] = useState<MaintenanceRequestRecord[] | null>(null)
  const [properties, setProperties] = useState<PropertyRecord[]>([])
  const [spaces, setSpaces] = useState<SpaceRecord[]>([])
  const [beds, setBeds] = useState<BedRecord[]>([])
  const [residents, setResidents] = useState<ResidentRecord[]>([])
  const [assignments, setAssignments] = useState<AssignmentRecord[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [attempt, setAttempt] = useState(0)
  const [propertyId, setPropertyId] = useState<string | undefined>()
  const [spaceId, setSpaceId] = useState<string | undefined>()
  const catalogRevision = useCatalogRevision()

  useEffect(() => {
    const controller = new AbortController()
    setPhase('loading')
    setMessage(null)
    const requestsPromise = listMaintenanceRequests(workspaceId, controller.signal)
    const extra = resident
      ? listAssignments(workspaceId, controller.signal).then((rows) => {
          setAssignments(rows)
        })
      : listProperties(workspaceId, controller.signal).then(async (propertyRows) => {
          const spaceRows = (
            await Promise.all(
              propertyRows.map((property) =>
                listSpaces(workspaceId, property.id, controller.signal),
              ),
            )
          ).flat()
          const bedRows = (
            await Promise.all(
              spaceRows.map((space) => listBeds(workspaceId, space.id, controller.signal)),
            )
          ).flat()
          const residentRows = await listResidents(workspaceId, controller.signal)
          const memberRows = triage
            ? await listMembers(workspaceId, controller.signal)
            : []
          if (controller.signal.aborted) {
            return
          }
          setProperties(propertyRows)
          setSpaces(spaceRows)
          setBeds(bedRows)
          setResidents(residentRows)
          setMembers(memberRows)
        })
    Promise.all([requestsPromise, extra])
      .then(([rows]) => {
        if (!controller.signal.aborted) {
          setRequests(rows)
          setPhase('ready')
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setPhase('error')
        setMessage(errorText(error))
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, resident, triage, attempt, catalogRevision])

  async function refresh() {
    setRequests(await listMaintenanceRequests(workspaceId))
  }

  async function handleFile(values: FileValues) {
    setActionMessage(null)
    try {
      const input: {
        description: string
        priority: string
        property_id?: string
        space_id?: string
        bed_id?: string
        resident_id?: string
        assignee_id?: string
      } = {
        description: values.description.trim(),
        priority: values.priority,
      }
      if (resident) {
        const [chosenSpace, chosenBed] = (values.place ?? '').split('|')
        if (chosenSpace) {
          input.space_id = chosenSpace
        }
        if (chosenBed) {
          input.bed_id = chosenBed
        }
      } else {
        if (values.property_id) {
          input.property_id = values.property_id
        }
        if (values.space_id) {
          input.space_id = values.space_id
        }
        if (values.bed_id) {
          input.bed_id = values.bed_id
        }
        if (values.resident_id) {
          input.resident_id = values.resident_id
        }
        if (values.assignee_id) {
          input.assignee_id = values.assignee_id
        }
      }
      await createMaintenanceRequest(workspaceId, input)
      await refresh()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  async function handleUpdate(requestId: string, values: UpdateValues) {
    setActionMessage(null)
    try {
      await updateMaintenanceRequest(workspaceId, requestId, {
        status: values.status,
        note: values.note?.trim(),
        completion_note: values.completion_note?.trim(),
        cost_amount: values.cost_amount?.trim() || undefined,
        assignee_id: triage ? values.assignee_id || undefined : undefined,
      })
      await refresh()
    } catch (error: unknown) {
      setActionMessage(errorText(error))
    }
  }

  const assignable = members.filter((member) =>
    ['owner', 'property_manager', 'maintenance'].includes(member.role),
  )
  const stayPlaces = assignments.filter(
    (row) => row.status === 'confirmed' || row.status === 'active',
  )

  return (
    <section id="maintenance">
      <PageHeader
        title="Maintenance"
        description={
          resident
            ? 'File a request for your own stay and follow its status. You cannot change the status or the cost.'
            : triage
              ? 'File a request for a property, room, or bed, then assign it. A request does not block the space.'
              : role === 'maintenance'
                ? 'You see requests assigned to you, and requests you filed that nobody has taken yet.'
                : 'You can file a request. The owner or property manager assigns it.'
        }
      />
      {phase === 'loading' ? (
        <Typography.Paragraph>Loading maintenance requests…</Typography.Paragraph>
      ) : null}
      {phase === 'error' ? (
        <Alert
          type="error"
          showIcon
          title="Maintenance requests could not be loaded"
          description={message}
          action={
            <Button size="small" onClick={() => setAttempt((value) => value + 1)}>
              Try again
            </Button>
          }
        />
      ) : null}
      {phase === 'ready' && requests?.length === 0 ? (
        <Empty
          description={resident ? 'You have not filed a request.' : 'No maintenance requests yet.'}
        />
      ) : null}
      {actionMessage ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The request was not saved"
          description={actionMessage}
        />
      ) : null}
      {phase === 'ready' ? (
        <Form<FileValues>
          className="form-panel"
          layout="vertical"
          requiredMark={false}
          initialValues={{ priority: 'normal' }}
          onFinish={(values) => {
            void handleFile(values)
          }}
        >
          <p className="form-panel-title">File a request</p>
          {resident ? (
            <Form.Item label="Place on your stay" name="place">
              <Select
                allowClear
                placeholder="No specific place"
                options={stayPlaces.map((row) => ({
                  value: `${row.space_id}|${row.bed_id ?? ''}`,
                  label: row.bed_name ? `${row.space_name} · ${row.bed_name}` : row.space_name,
                }))}
              />
            </Form.Item>
          ) : (
            <>
              <Form.Item
                label="Property"
                name="property_id"
                rules={[{ required: true, message: 'Choose a property.' }]}
              >
                <Select
                  options={properties.map((row) => ({ value: row.id, label: row.name }))}
                  onChange={(value: string) => {
                    setPropertyId(value)
                    setSpaceId(undefined)
                  }}
                />
              </Form.Item>
              <Form.Item label="Space" name="space_id">
                <Select
                  allowClear
                  options={spaces
                    .filter((row) => row.property_id === propertyId)
                    .map((row) => ({ value: row.id, label: row.name }))}
                  onChange={(value: string) => setSpaceId(value)}
                />
              </Form.Item>
              <Form.Item label="Bed" name="bed_id">
                <Select
                  allowClear
                  options={beds
                    .filter((row) => row.space_id === spaceId)
                    .map((row) => ({ value: row.id, label: row.name }))}
                />
              </Form.Item>
              <Form.Item label="Resident" name="resident_id">
                <Select
                  allowClear
                  options={residents.map((row) => ({
                    value: row.id,
                    label: `${row.first_name} ${row.last_name}`,
                  }))}
                />
              </Form.Item>
              {triage ? (
                <Form.Item label="Assign to" name="assignee_id">
                  <Select
                    allowClear
                    options={assignable.map((member) => ({
                      value: member.user.id,
                      label: member.user.email,
                    }))}
                  />
                </Form.Item>
              ) : null}
            </>
          )}
          <Form.Item
            label="Description"
            name="description"
            rules={[{ required: true, message: 'Describe the problem.' }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item
            label="Priority"
            name="priority"
            rules={[{ required: true, message: 'Choose a priority.' }]}
          >
            <Select options={PRIORITIES} />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            File request
          </Button>
        </Form>
      ) : null}
      {requests && requests.length > 0 ? (
        <Table
          className="data-table"
          style={{ marginTop: 16 }}
          rowKey="id"
          pagination={false}
          dataSource={requests}
          scroll={{ x: 'max-content' }}
          columns={[
            {
              title: 'Request',
              render: (_value, row) => (
                <div>
                  <span>
                    {row.reference} · {row.priority} · {row.status}
                  </span>
                  <Typography.Paragraph style={{ margin: '4px 0 0' }}>
                    {placeLabel(row)}.
                    {row.resident_name ? ` ${row.resident_name}.` : ''}
                  </Typography.Paragraph>
                  {row.location_blocked ? (
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      This place is already unavailable for maintenance. The request does not change that.
                    </Typography.Paragraph>
                  ) : null}
                  {row.cost_amount ? (
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      Cost {formatMoney(row.cost_amount, row.currency_code)}.
                    </Typography.Paragraph>
                  ) : null}
                  {row.assignee_email ? (
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      Assigned to {row.assignee_email}.
                    </Typography.Paragraph>
                  ) : null}
                </div>
              ),
            },
            {
              title: 'Status',
              render: (_value, row) => <StatusTag value={row.status} />,
            },
            { title: 'Description', dataIndex: 'description' },
            {
              title: 'Updates',
              render: (_value, row) => (
                <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                  {row.updates.map((update) => (
                    <li key={update.id}>
                      {update.status_before ? `${update.status_before} → ` : ''}
                      {update.status_after}
                      {update.note ? `. ${update.note}` : ''}
                    </li>
                  ))}
                </ul>
              ),
            },
          ]}
        />
      ) : null}
      {canUpdate
        ? requests?.map((row) => (
            <Form<UpdateValues>
              key={row.id}
              className="form-panel"
              layout="vertical"
              requiredMark={false}
              initialValues={{ status: row.status, assignee_id: row.assignee_id ?? undefined }}
              onFinish={(values) => {
                void handleUpdate(row.id, values)
              }}
            >
              <p className="form-panel-title">Update {row.reference}</p>
              <Form.Item label={`Status for ${row.reference}`} name="status">
                <Select options={STATUSES} />
              </Form.Item>
              {triage ? (
                <Form.Item label={`Assign ${row.reference}`} name="assignee_id">
                  <Select
                    allowClear
                    options={assignable.map((member) => ({
                      value: member.user.id,
                      label: member.user.email,
                    }))}
                  />
                </Form.Item>
              ) : null}
              <Form.Item label={`Note for ${row.reference}`} name="note">
                <Input />
              </Form.Item>
              <Form.Item label={`Completion note for ${row.reference}`} name="completion_note">
                <Input />
              </Form.Item>
              <Form.Item label={`Cost for ${row.reference}`} name="cost_amount">
                <Input inputMode="decimal" />
              </Form.Item>
              <Button htmlType="submit">Save {row.reference}</Button>
            </Form>
          ))
        : null}
    </section>
  )
}
