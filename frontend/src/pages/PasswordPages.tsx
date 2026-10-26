import { Alert, Button, Card, ConfigProvider, Form, Input, Typography } from 'antd'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  changePassword,
  confirmPasswordReset,
  errorText,
  requestPasswordReset,
} from '../api/session'
import { theme } from '../theme'

function AuthCard({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <ConfigProvider theme={theme}>
      <main>
        <Card style={{ maxWidth: 480, margin: '48px auto', width: 'calc(100% - 32px)' }}>
          <Typography.Title level={1} style={{ marginTop: 0, fontSize: '1.7rem' }}>
            Rent It HQ
          </Typography.Title>
          <Typography.Title level={2} style={{ marginTop: 0, fontSize: '1.5rem' }}>
            {title}
          </Typography.Title>
          {children}
        </Card>
      </main>
    </ConfigProvider>
  )
}

export function ForgotPasswordPage() {
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'Forgot password · Rent It HQ'
  }, [])

  async function handleFinish(values: { email: string }) {
    setSubmitting(true)
    setError(null)
    try {
      setMessage(await requestPasswordReset(values.email.trim()))
    } catch (caught: unknown) {
      setError(errorText(caught))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthCard title="Forgot password">
      <Typography.Paragraph>
        Enter the email on the account. If it matches, a reset link is sent. The reply is the
        same either way.
      </Typography.Paragraph>
      {message ? <Alert type="success" showIcon title={message} /> : null}
      {error ? (
        <Alert type="error" showIcon style={{ marginBottom: 16 }} title="That did not work" description={error} />
      ) : null}
      {message ? null : (
        <Form layout="vertical" requiredMark={false} onFinish={handleFinish}>
          <Form.Item
            label="Email"
            name="email"
            rules={[{ required: true, message: 'Enter your email.' }]}
          >
            <Input type="email" autoComplete="email" inputMode="email" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting}>
            Send reset link
          </Button>
        </Form>
      )}
      <div style={{ marginTop: 16 }}>
        <Link to="/login">Back to sign in</Link>
      </div>
    </AuthCard>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''

  useEffect(() => {
    document.title = 'Reset password · Rent It HQ'
  }, [])

  async function handleFinish(values: { password: string; confirm: string }) {
    if (values.password !== values.confirm) {
      setError('The two passwords do not match.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      setMessage(
        await confirmPasswordReset({
          uid,
          token,
          password: values.password,
        }),
      )
    } catch (caught: unknown) {
      setError(errorText(caught))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthCard title="Reset password">
      <Typography.Paragraph>
        Choose a new password. The link works once and expires after one hour.
      </Typography.Paragraph>
      {message ? <Alert type="success" showIcon title={message} /> : null}
      {error ? (
        <Alert type="error" showIcon style={{ marginBottom: 16 }} title="That did not work" description={error} />
      ) : null}
      {message ? null : (
        <Form layout="vertical" requiredMark={false} onFinish={handleFinish}>
          <Form.Item
            label="New password"
            name="password"
            rules={[{ required: true, message: 'Choose a password.' }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            label="Confirm password"
            name="confirm"
            rules={[{ required: true, message: 'Enter the password again.' }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting}>
            Update password
          </Button>
        </Form>
      )}
      <div style={{ marginTop: 16 }}>
        <Link to="/login">Sign in</Link>
      </div>
    </AuthCard>
  )
}

export function ChangePasswordForm() {
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFinish(values: { current_password: string; password: string }) {
    setSubmitting(true)
    setError(null)
    setMessage(null)
    try {
      setMessage(
        await changePassword({
          current_password: values.current_password,
          password: values.password,
        }),
      )
    } catch (caught: unknown) {
      setError(errorText(caught))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section style={{ marginBottom: 24 }}>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Password
      </Typography.Title>
      <Typography.Paragraph>
        Changing it asks for the current password and keeps this sign-in.
      </Typography.Paragraph>
      {message ? <Alert type="success" showIcon style={{ marginBottom: 16 }} title={message} /> : null}
      {error ? (
        <Alert type="error" showIcon style={{ marginBottom: 16 }} title="The password was not changed" description={error} />
      ) : null}
      <Form layout="vertical" requiredMark={false} onFinish={handleFinish} style={{ maxWidth: 420 }}>
        <Form.Item
          label="Current password"
          name="current_password"
          rules={[{ required: true, message: 'Enter your current password.' }]}
        >
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Form.Item
          label="New password"
          name="password"
          rules={[{ required: true, message: 'Choose a new password.' }]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={submitting}>
          Change password
        </Button>
      </Form>
    </section>
  )
}
