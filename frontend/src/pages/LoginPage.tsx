import { Alert, Button, Card, ConfigProvider, Form, Input, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  errorText,
  loadSession,
  registerAccount,
  signIn,
} from '../api/session'
import { theme } from '../theme'

type SignInValues = {
  email: string
  password: string
}

type RegisterValues = SignInValues & {
  first_name?: string
  last_name?: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [mode, setMode] = useState<'sign-in' | 'register'>(
    params.get('mode') === 'register' ? 'register' : 'sign-in',
  )
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    document.title = mode === 'sign-in' ? 'Sign in · Rent It HQ' : 'Create an account · Rent It HQ'
    const controller = new AbortController()
    loadSession(controller.signal)
      .then((session) => {
        if (session && !controller.signal.aborted) {
          navigate('/app', { replace: true })
        }
      })
      .catch(() => {
        // Stay on the form when the session cannot be checked.
      })
    return () => {
      controller.abort()
    }
  }, [mode, navigate])

  async function handleSignIn(values: SignInValues) {
    setSubmitting(true)
    setMessage(null)
    try {
      await signIn({
        email: values.email.trim(),
        password: values.password,
      })
      navigate('/app', { replace: true })
    } catch (error: unknown) {
      setMessage(errorText(error))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRegister(values: RegisterValues) {
    setSubmitting(true)
    setMessage(null)
    try {
      await registerAccount({
        email: values.email.trim(),
        password: values.password,
        first_name: values.first_name?.trim() ?? '',
        last_name: values.last_name?.trim() ?? '',
      })
      navigate('/app', { replace: true })
    } catch (error: unknown) {
      setMessage(errorText(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <ConfigProvider theme={theme}>
      <main className="auth-frame">
        <Card>
          <Typography.Title level={1} style={{ marginTop: 0, fontSize: '1.7rem' }}>
            Rent It HQ
          </Typography.Title>
          <Typography.Title level={2} style={{ marginTop: 0, fontSize: '1.5rem' }}>
            {mode === 'sign-in' ? 'Sign in' : 'Create an account'}
          </Typography.Title>
          <Typography.Paragraph>
            {mode === 'sign-in'
              ? 'Use the email and password for your Rent It HQ account.'
              : 'Create an account, then open a workspace. This does not make you a platform operator.'}
          </Typography.Paragraph>
          {message ? (
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
              title="That did not work"
              description={message}
            />
          ) : null}
          {mode === 'sign-in' ? (
            <Form<SignInValues> layout="vertical" onFinish={handleSignIn} requiredMark={false}>
              <Form.Item
                label="Email"
                name="email"
                rules={[{ required: true, message: 'Enter your email.' }]}
              >
                <Input type="email" autoComplete="email" inputMode="email" />
              </Form.Item>
              <Form.Item
                label="Password"
                name="password"
                rules={[{ required: true, message: 'Enter your password.' }]}
              >
                <Input.Password autoComplete="current-password" />
              </Form.Item>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <Button type="primary" htmlType="submit" loading={submitting}>
                  Sign in
                </Button>
                <Link to="/forgot-password">Forgot password?</Link>
              </div>
            </Form>
          ) : (
            <Form<RegisterValues> layout="vertical" onFinish={handleRegister} requiredMark={false}>
              <Form.Item
                label="Email"
                name="email"
                rules={[{ required: true, message: 'Enter your email.' }]}
              >
                <Input type="email" autoComplete="email" inputMode="email" />
              </Form.Item>
              <Form.Item label="First name" name="first_name">
                <Input autoComplete="given-name" />
              </Form.Item>
              <Form.Item label="Last name" name="last_name">
                <Input autoComplete="family-name" />
              </Form.Item>
              <Form.Item
                label="Password"
                name="password"
                rules={[{ required: true, message: 'Choose a password.' }]}
              >
                <Input.Password autoComplete="new-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={submitting}>
                Create account
              </Button>
            </Form>
          )}
          <Button
            type="link"
            style={{ paddingInline: 0, marginTop: 12 }}
            onClick={() => {
              setMode(mode === 'sign-in' ? 'register' : 'sign-in')
              setMessage(null)
            }}
          >
            {mode === 'sign-in' ? 'Create an account' : 'Already have an account? Sign in'}
          </Button>
        </Card>
      </main>
    </ConfigProvider>
  )
}
