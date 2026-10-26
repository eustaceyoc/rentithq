import { ApiError } from './client'

export type SessionUser = {
  id: string
  email: string
  first_name: string
  last_name: string
}

export type WorkspaceSummary = {
  id: string
  name: string
  currency_code: string
  timezone: string
  status: string
  plan_code?: string
}

export type SessionMembership = {
  id: string
  role: string
  workspace: WorkspaceSummary
}

export type SessionPayload = {
  user: SessionUser
  memberships: SessionMembership[]
}

export type Member = {
  id: string
  role: string
  user: SessionUser
}

let csrfToken: string | null = null

export function resetApiState(): void {
  csrfToken = null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function textField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key]
  return typeof value === 'string' ? value : null
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length))
    }
  }
  return null
}

function fieldMessages(details: unknown): Record<string, string> {
  const fields: Record<string, string> = {}
  if (!isRecord(details)) {
    return fields
  }
  for (const [key, value] of Object.entries(details)) {
    if (typeof value === 'string') {
      fields[key] = value
    } else if (Array.isArray(value) && typeof value[0] === 'string') {
      fields[key] = value[0]
    }
  }
  return fields
}

export async function errorFromResponse(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json()
    if (isRecord(body) && isRecord(body.error)) {
      const code = textField(body.error, 'code') ?? 'error'
      const message =
        textField(body.error, 'message') ?? 'The request could not be completed.'
      const fields = fieldMessages(body.error.details)
      const specific = fields.non_field_errors ?? fields.detail
      return new ApiError(specific ?? message, code, fields)
    }
  } catch (error: unknown) {
    if (isAbort(error)) {
      throw error
    }
  }
  return new ApiError('The request could not be completed.')
}

async function ensureCsrf(signal?: AbortSignal): Promise<string> {
  if (csrfToken) {
    return csrfToken
  }
  const fromCookie = readCookie('csrftoken')
  if (fromCookie) {
    csrfToken = fromCookie
    return fromCookie
  }
  let response: Response
  try {
    response = await fetch('/api/v1/auth/csrf/', {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error: unknown) {
    if (isAbort(error)) {
      throw error
    }
    throw new ApiError('Your session could not be checked.')
  }
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  let body: unknown
  try {
    body = await response.json()
  } catch (error: unknown) {
    if (isAbort(error)) {
      throw error
    }
    throw new ApiError('The API returned an unexpected response.')
  }
  if (!isRecord(body) || typeof body.csrfToken !== 'string' || !body.csrfToken) {
    throw new ApiError('The API returned an unexpected response.')
  }
  csrfToken = body.csrfToken
  return body.csrfToken
}

export async function request(
  path: string,
  options: {
    method?: string
    body?: unknown
    workspaceId?: string
    signal?: AbortSignal
  } = {},
): Promise<Response> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRFToken'] = await ensureCsrf(options.signal)
  }
  if (options.workspaceId) {
    headers['X-Workspace-Id'] = options.workspaceId
  }
  try {
    return await fetch(path, {
      method,
      credentials: 'include',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    })
  } catch (error: unknown) {
    if (isAbort(error)) {
      throw error
    }
    throw new ApiError('Your session could not be checked.')
  }
}

function isUser(value: unknown): value is SessionUser {
  if (!isRecord(value)) {
    return false
  }
  return (
    textField(value, 'id') !== null &&
    textField(value, 'email') !== null &&
    textField(value, 'first_name') !== null &&
    textField(value, 'last_name') !== null
  )
}

function isWorkspace(value: unknown): value is WorkspaceSummary {
  if (!isRecord(value)) {
    return false
  }
  return (
    textField(value, 'id') !== null &&
    textField(value, 'name') !== null &&
    textField(value, 'currency_code') !== null &&
    textField(value, 'timezone') !== null &&
    textField(value, 'status') !== null
  )
}

function isSession(value: unknown): value is SessionPayload {
  if (!isRecord(value) || !isUser(value.user) || !Array.isArray(value.memberships)) {
    return false
  }
  return value.memberships.every(
    (membership) =>
      isRecord(membership) &&
      textField(membership, 'id') !== null &&
      textField(membership, 'role') !== null &&
      isWorkspace(membership.workspace),
  )
}

function isMember(value: unknown): value is Member {
  if (!isRecord(value) || !isUser(value.user)) {
    return false
  }
  return textField(value, 'id') !== null && textField(value, 'role') !== null
}

async function readSession(response: Response): Promise<SessionPayload> {
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  let body: unknown
  try {
    body = await response.json()
  } catch (error: unknown) {
    if (isAbort(error)) {
      throw error
    }
    throw new ApiError('The API returned an unexpected response.')
  }
  if (!isSession(body)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body
}

export async function loadSession(
  signal?: AbortSignal,
): Promise<SessionPayload | null> {
  const response = await request('/api/v1/auth/session/', { signal })
  if (response.status === 401 || response.status === 403) {
    const error = await errorFromResponse(response)
    if (error.code === 'not_authenticated' || response.status === 401) {
      return null
    }
    throw error
  }
  return readSession(response)
}

function adoptRotatedCsrfCookie(): void {
  // Django rotates the CSRF token on login. The cached pre-login token would
  // fail the next unsafe request.
  csrfToken = readCookie('csrftoken')
}

export async function registerAccount(input: {
  email: string
  password: string
  first_name: string
  last_name: string
}): Promise<SessionPayload> {
  const response = await request('/api/v1/auth/register/', {
    method: 'POST',
    body: input,
  })
  const session = await readSession(response)
  adoptRotatedCsrfCookie()
  return session
}

export async function signIn(input: {
  email: string
  password: string
}): Promise<SessionPayload> {
  const response = await request('/api/v1/auth/login/', {
    method: 'POST',
    body: input,
  })
  const session = await readSession(response)
  adoptRotatedCsrfCookie()
  return session
}

export async function signOut(): Promise<void> {
  const response = await request('/api/v1/auth/logout/', { method: 'POST' })
  csrfToken = null
  if (!response.ok && response.status !== 204) {
    throw await errorFromResponse(response)
  }
}

export async function createWorkspace(input: {
  name: string
  currency_code: string
  timezone: string
}): Promise<WorkspaceSummary> {
  const response = await request('/api/v1/workspaces/', {
    method: 'POST',
    body: input,
  })
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError('The API returned an unexpected response.')
  }
  if (!isWorkspace(body)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body
}

export async function listMembers(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<Member[]> {
  const response = await request('/api/v1/memberships/', {
    workspaceId,
    signal,
  })
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  let body: unknown
  try {
    body = await response.json()
  } catch (error: unknown) {
    if (isAbort(error)) {
      throw error
    }
    throw new ApiError('The API returned an unexpected response.')
  }
  if (!isRecord(body) || !Array.isArray(body.results)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  if (!body.results.every(isMember)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body.results
}

export async function addMember(
  workspaceId: string,
  input: { email: string; role: string },
): Promise<void> {
  const response = await request('/api/v1/memberships/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
}

export async function removeMember(
  workspaceId: string,
  membershipId: string,
): Promise<void> {
  const response = await request(`/api/v1/memberships/${membershipId}/`, {
    method: 'DELETE',
    workspaceId,
  })
  if (!response.ok && response.status !== 204) {
    throw await errorFromResponse(response)
  }
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    return (
      error.fields.non_field_errors ??
      error.fields.detail ??
      Object.values(error.fields)[0] ??
      error.message
    )
  }
  return 'The request could not be completed.'
}
