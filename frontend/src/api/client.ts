export class ApiError extends Error {
  readonly code: string
  readonly fields: Readonly<Record<string, string>>

  constructor(
    message: string,
    code = 'error',
    fields: Record<string, string> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.fields = fields
  }
}

export type HealthResponse = {
  status: string
  service?: string
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  if (typeof record.status !== 'string') {
    return false
  }
  return record.service === undefined || typeof record.service === 'string'
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  let response: Response
  try {
    response = await fetch('/api/v1/health/', {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError('The API could not be reached.')
  }

  if (!response.ok) {
    throw new ApiError('The API returned an error.')
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError('The API returned an unexpected response.')
  }
  if (!isHealthResponse(body)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body
}
