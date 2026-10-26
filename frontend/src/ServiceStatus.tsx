import { Alert, Card, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { ApiError, getHealth, type HealthResponse } from './api/client'

type Phase = 'loading' | 'ready' | 'error'

export function ServiceStatus() {
  const [phase, setPhase] = useState<Phase>('loading')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [message, setMessage] = useState('Checking the API…')

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((body) => {
        setHealth(body)
        setPhase('ready')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setPhase('error')
        setMessage(
          error instanceof ApiError ? error.message : 'The API could not be reached.',
        )
      })
    return () => {
      controller.abort()
    }
  }, [])

  const reportedHealthy = health?.status === 'ok'

  return (
    <Card style={{ maxWidth: 720, margin: '24px auto' }}>
      <Typography.Title level={2} style={{ marginTop: 0, fontSize: '1.5rem' }}>
        API connection
      </Typography.Title>
      <Typography.Paragraph>
        This screen asks the API whether the service is up. It does not change
        workspace data.
      </Typography.Paragraph>
      <div aria-live="polite">
        {phase === 'loading' ? (
          <Spin description="Checking the API…">
            <div style={{ minHeight: 48 }} />
          </Spin>
        ) : null}
        {phase === 'ready' && reportedHealthy ? (
          <Alert
            type="success"
            showIcon
            title="The API is reachable."
            description={
              health?.service
                ? `Service: ${health.service}. Reported status: ${health.status}.`
                : `Reported status: ${health?.status}.`
            }
          />
        ) : null}
        {phase === 'ready' && !reportedHealthy ? (
          <Alert
            type="warning"
            showIcon
            title="The API responded, but it is not reporting a healthy status."
            description={`Reported status: ${health?.status ?? 'unknown'}.`}
          />
        ) : null}
        {phase === 'error' ? (
          <Alert
            type="error"
            showIcon
            title="The API could not be reached."
            description={
              message === 'The API could not be reached.'
                ? 'The web app could not get a usable response from the API.'
                : message
            }
          />
        ) : null}
      </div>
    </Card>
  )
}
