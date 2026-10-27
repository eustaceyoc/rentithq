import {
  Alert,
  Button,
  Card,
  ConfigProvider,
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
import { Navigate } from 'react-router-dom'
import {
  addMember,
  createWorkspace,
  errorText,
  listMembers,
  loadSession,
  removeMember,
  signOut,
  type Member,
  type SessionMembership,
  type SessionPayload,
  type WorkspaceSummary,
} from './api/session'
import { ChangePasswordForm } from './pages/PasswordPages'
import { WorkspaceRoutes } from './pages/WorkspaceRoutes'
import { AppShell } from './shell/AppShell'
import { theme } from './theme'
import { PageHeader } from './ui/PageHeader'

const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner',
  property_manager: 'Property manager',
  finance: 'Finance',
  maintenance: 'Maintenance',
  resident: 'Resident',
}

const INVITE_ROLES = [
  { value: 'property_manager', label: 'Property manager' },
  { value: 'finance', label: 'Finance' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'resident', label: 'Resident' },
  { value: 'owner', label: 'Owner' },
]

function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role
}

type WorkspaceValues = {
  name: string
  currency_code: string
  timezone?: string
}

type InviteValues = {
  email: string
  role: string
}

function CreateWorkspaceForm({
  onCreated,
}: {
  onCreated: (workspace: WorkspaceSummary) => void
}) {
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function handleFinish(values: WorkspaceValues) {
    setSubmitting(true)
    setMessage(null)
    try {
      const workspace = await createWorkspace({
        name: values.name.trim(),
        currency_code: values.currency_code.trim().toUpperCase(),
        timezone: values.timezone?.trim() || 'UTC',
      })
      onCreated(workspace)
    } catch (error: unknown) {
      setMessage(errorText(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Typography.Title level={2} style={{ marginTop: 0, fontSize: '1.5rem' }}>
        Create a workspace
      </Typography.Title>
      <Typography.Paragraph>
        You do not belong to a workspace yet. Create one to continue. You become
        its owner. One currency covers the whole workspace.
      </Typography.Paragraph>
      {message ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="The workspace was not created"
          description={message}
        />
      ) : null}
      <Form<WorkspaceValues>
        layout="vertical"
        requiredMark={false}
        initialValues={{ timezone: 'UTC' }}
        onFinish={handleFinish}
      >
        <Form.Item
          label="Workspace name"
          name="name"
          rules={[{ required: true, message: 'Enter a workspace name.' }]}
        >
          <Input autoComplete="organization" />
        </Form.Item>
        <Form.Item
          label="Currency"
          name="currency_code"
          extra="Three uppercase letters, such as GHS or USD."
          rules={[{ required: true, message: 'Enter a currency code.' }]}
        >
          <Input maxLength={3} autoCapitalize="characters" spellCheck={false} />
        </Form.Item>
        <Form.Item
          label="Timezone"
          name="timezone"
          extra="An IANA name, such as Africa/Accra. Stored times stay in UTC."
        >
          <Input spellCheck={false} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={submitting}>
          Create workspace
        </Button>
      </Form>
    </>
  )
}

function WorkspaceChooser({
  memberships,
  onChoose,
}: {
  memberships: SessionMembership[]
  onChoose: (workspaceId: string) => void
}) {
  return (
    <>
      <Typography.Title level={2} style={{ marginTop: 0, fontSize: '1.5rem' }}>
        Choose a workspace
      </Typography.Title>
      <Typography.Paragraph>
        You belong to more than one workspace. Open the one you want to work in.
        The server only accepts a workspace you already belong to.
      </Typography.Paragraph>
      <div style={{ display: 'grid', gap: 8 }}>
        {memberships.map((membership) => (
          <Button
            key={membership.workspace.id}
            onClick={() => {
              onChoose(membership.workspace.id)
            }}
          >
            {membership.workspace.name} · {roleLabel(membership.role)}
          </Button>
        ))}
      </div>
    </>
  )
}

function WorkspacePanel({
  session,
  membership,
  onSwitch,
  onSignOut,
}: {
  session: SessionPayload
  membership: SessionMembership
  onSwitch: (() => void) | null
  onSignOut: () => void
}) {
  const workspace = membership.workspace
  const [members, setMembers] = useState<Member[] | null>(null)
  const [memberMessage, setMemberMessage] = useState<string | null>(null)
  const [inviteMessage, setInviteMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [inviting, setInviting] = useState(false)
  const available = workspace.status === 'active'
  const isOwner = membership.role === 'owner'

  useEffect(() => {
    if (!available) {
      return
    }
    const controller = new AbortController()
    listMembers(workspace.id, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) {
          setMembers(rows)
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setMemberMessage(errorText(error))
      })
    return () => {
      controller.abort()
    }
  }, [available, reloadKey, workspace.id])

  async function handleInvite(values: InviteValues) {
    setInviting(true)
    setInviteMessage(null)
    try {
      await addMember(workspace.id, {
        email: values.email.trim(),
        role: values.role,
      })
      setMembers(null)
      setMemberMessage(null)
      setReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setInviteMessage(errorText(error))
    } finally {
      setInviting(false)
    }
  }

  async function handleRemove(membershipId: string) {
    setInviteMessage(null)
    try {
      await removeMember(workspace.id, membershipId)
      setMembers(null)
      setMemberMessage(null)
      setReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setInviteMessage(errorText(error))
    }
  }

  const [inviteOpen, setInviteOpen] = useState(false)
  const settings = (
    <>
      <PageHeader
        title="Settings"
        description={
          <>
            Currency {workspace.currency_code}. Timezone {workspace.timezone}.
            {workspace.plan_code ? ` Account plan ${workspace.plan_code}.` : ''}
          </>
        }
      />
      <div className="form-panel" style={{ marginTop: 0, marginBottom: 24 }}>
        <ChangePasswordForm />
      </div>
      <Card title="People">
          {membership.role === 'resident' ? (
            <Typography.Paragraph>
              You can see your own membership. Workspace settings stay with the owner.
            </Typography.Paragraph>
          ) : (
            <Typography.Paragraph>
              People in this workspace only. Accounts from other workspaces are not listed here.
            </Typography.Paragraph>
          )}
          {memberMessage ? (
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
              title="Members could not be loaded"
              description={memberMessage}
            />
          ) : null}
          {members === null && !memberMessage ? (
            <Typography.Paragraph>Loading members…</Typography.Paragraph>
          ) : null}
          {members && members.length === 0 ? (
            <Empty description="No members are visible in this workspace." />
          ) : null}
          {members && members.length > 0 ? (
            <Table
              className="data-table"
              rowKey="id"
              pagination={false}
              dataSource={members}
              scroll={{ x: 'max-content' }}
              columns={[
                {
                  title: 'Email',
                  dataIndex: ['user', 'email'],
                  render: (_value, member) => member.user.email,
                },
                {
                  title: 'Role',
                  dataIndex: 'role',
                  render: (role: string) => <Tag>{roleLabel(role)}</Tag>,
                },
                {
                  title: '',
                  key: 'actions',
                  render: (_value, member) =>
                    isOwner && member.user.id !== session.user.id ? (
                      <Popconfirm
                        title={`Remove ${member.user.email} from this workspace?`}
                        okText="Remove"
                        cancelText="Cancel"
                        onConfirm={() => {
                          void handleRemove(member.id)
                        }}
                      >
                        <Button danger size="small">
                          Remove {member.user.email}
                        </Button>
                      </Popconfirm>
                    ) : null,
                },
              ]}
            />
          ) : null}
          {isOwner ? (
            <>
              <Button
                type="primary"
                style={{ marginTop: 16 }}
                onClick={() => {
                  setInviteOpen(true)
                }}
              >
                Add member
              </Button>
              <Modal
                title="Add someone who already has an account"
                open={inviteOpen}
                onCancel={() => {
                  setInviteOpen(false)
                }}
                footer={null}
                destroyOnHidden
              >
                {inviteMessage ? (
                  <Alert
                    type="error"
                    showIcon
                    style={{ marginBottom: 16 }}
                    title="The member was not added"
                    description={inviteMessage}
                  />
                ) : null}
                <Form<InviteValues>
                  key={reloadKey}
                  layout="vertical"
                  requiredMark={false}
                  initialValues={{ role: 'property_manager' }}
                  onFinish={handleInvite}
                >
                  <Form.Item
                    label="Email"
                    name="email"
                    rules={[{ required: true, message: 'Enter an email.' }]}
                  >
                    <Input type="email" autoComplete="off" inputMode="email" />
                  </Form.Item>
                  <Form.Item
                    label="Role"
                    name="role"
                    rules={[{ required: true, message: 'Choose a role.' }]}
                  >
                    <Select options={INVITE_ROLES} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={inviting}>
                    Add member
                  </Button>
                </Form>
              </Modal>
            </>
          ) : null}
    </Card>
    </>
  )

  return (
    <AppShell
      workspaceName={workspace.name}
      role={membership.role}
      roleName={roleLabel(membership.role)}
      email={session.user.email}
      onSignOut={onSignOut}
      onSwitch={onSwitch}
    >
      {!available ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          title="This workspace is not available."
          description="A platform operator has to restore it before anyone can change it."
        />
      ) : null}
      <WorkspaceRoutes
        workspaceId={workspace.id}
        role={membership.role}
        currency={workspace.currency_code}
        available={available}
        settings={settings}
      />
    </AppShell>
  )
}

export function WorkspaceHome() {
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [message, setMessage] = useState('Checking your session…')
  const [session, setSession] = useState<SessionPayload | null>(null)
  const [pickedId, setPickedId] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    loadSession(controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) {
          setSession(next)
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
  }, [attempt])

  const memberships = session?.memberships ?? []
  const picked = pickedId
    ? memberships.find((membership) => membership.workspace.id === pickedId)
    : undefined
  const selected = picked ?? (memberships.length === 1 ? memberships[0] : undefined)

  async function handleSignOut() {
    try {
      await signOut()
    } catch {
      // The local screen still returns to sign-in. The cookie is the authority.
    }
    setSession(null)
    setPickedId(null)
    setPhase('ready')
  }

  let body = null
  if (phase === 'loading') {
    body = <Typography.Paragraph>Checking your session…</Typography.Paragraph>
  } else if (phase === 'error') {
    body = (
      <Alert
        type="error"
        showIcon
        title="Your session could not be checked."
        description={message}
        action={
            <Button
            size="small"
            onClick={() => {
              setPhase('loading')
              setMessage('Checking your session…')
              setAttempt((value) => value + 1)
            }}
          >
            Try again
          </Button>
        }
      />
    )
  } else if (!session) {
    body = <Navigate to="/login" replace />
  } else if (memberships.length === 0) {
    body = (
      <CreateWorkspaceForm
        onCreated={(workspace) => {
          void loadSession().then((next) => {
            if (next && next.memberships.some((item) => item.workspace.id === workspace.id)) {
              setSession(next)
            } else {
              setSession({
                ...session,
                memberships: [
                  {
                    id: `local-${workspace.id}`,
                    role: 'owner',
                    workspace,
                  },
                ],
              })
            }
            setPickedId(workspace.id)
          })
        }}
      />
    )
  } else if (!selected) {
    body = (
      <WorkspaceChooser
        memberships={memberships}
        onChoose={(workspaceId) => {
          setPickedId(workspaceId)
        }}
      />
    )
  } else {
    body = (
      <WorkspacePanel
        key={selected.workspace.id}
        session={session}
        membership={selected}
        onSwitch={
          memberships.length > 1
            ? () => {
                setPickedId(null)
              }
            : null
        }
        onSignOut={() => {
          void handleSignOut()
        }}
      />
    )
  }

  if (selected) {
    return <ConfigProvider theme={theme}>{body}</ConfigProvider>
  }

  return (
    <ConfigProvider theme={theme}>
    <main className="auth-frame">
    <Card>
      <Typography.Title level={1} style={{ marginTop: 0, fontSize: '1.7rem' }}>
        Rent It HQ
      </Typography.Title>
      <div aria-live="polite">
        {session ? (
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 12,
              flexWrap: 'wrap',
              marginBottom: 16,
            }}
          >
            <Typography.Text>{session.user.email}</Typography.Text>
            <Button onClick={() => void handleSignOut()}>Sign out</Button>
          </div>
        ) : null}
        {body}
      </div>
    </Card>
    </main>
    </ConfigProvider>
  )
}
