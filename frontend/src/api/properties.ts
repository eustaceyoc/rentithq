import { ApiError } from './client'
import { errorFromResponse, request } from './session'

export type PropertyRecord = {
  id: string
  name: string
  address: string
}

export type BuildingRecord = {
  id: string
  property_id: string
  name: string
}

export type FloorRecord = {
  id: string
  property_id: string
  building_id: string | null
  name: string
}

export type SpaceKind = 'unit' | 'room'
export type Availability = 'active' | 'inactive' | 'unavailable'
export type BlockReason = '' | 'maintenance'

export type SpaceRecord = {
  id: string
  property_id: string
  building_id: string | null
  floor_id: string | null
  name: string
  kind: SpaceKind
  availability: Availability
  block_reason: BlockReason
}

export type BedRecord = {
  id: string
  space_id: string
  name: string
  availability: Availability
  block_reason: BlockReason
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function text(value: Record<string, unknown>, key: string): string | null {
  const field = value[key]
  return typeof field === 'string' ? field : null
}

function optionalId(
  value: Record<string, unknown>,
  key: string,
): string | null | undefined {
  const field = value[key]
  if (field === null) {
    return null
  }
  return typeof field === 'string' ? field : undefined
}

async function readBody(response: Response): Promise<unknown> {
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  try {
    return await response.json()
  } catch {
    throw new ApiError('The API returned an unexpected response.')
  }
}

function pageItems(body: unknown): unknown[] {
  if (!isRecord(body) || !Array.isArray(body.results)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body.results
}

function parseProperty(value: unknown): PropertyRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const name = text(value, 'name')
  const address = text(value, 'address')
  if (id === null || name === null || address === null) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return { id, name, address }
}

function parseBuilding(value: unknown): BuildingRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const propertyId = text(value, 'property_id')
  const name = text(value, 'name')
  if (id === null || propertyId === null || name === null) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return { id, property_id: propertyId, name }
}

function parseFloor(value: unknown): FloorRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const propertyId = text(value, 'property_id')
  const buildingId = optionalId(value, 'building_id')
  const name = text(value, 'name')
  if (
    id === null ||
    propertyId === null ||
    buildingId === undefined ||
    name === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return { id, property_id: propertyId, building_id: buildingId, name }
}

function parseAvailability(value: string | null): Availability | null {
  if (value === 'active' || value === 'inactive' || value === 'unavailable') {
    return value
  }
  return null
}

function parseBlock(value: string | null): BlockReason | null {
  if (value === '' || value === 'maintenance') {
    return value
  }
  return null
}

function parseSpace(value: unknown): SpaceRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const propertyId = text(value, 'property_id')
  const buildingId = optionalId(value, 'building_id')
  const floorId = optionalId(value, 'floor_id')
  const name = text(value, 'name')
  const kind = text(value, 'kind')
  const availability = parseAvailability(text(value, 'availability'))
  const blockReason = parseBlock(text(value, 'block_reason'))
  if (
    id === null ||
    propertyId === null ||
    buildingId === undefined ||
    floorId === undefined ||
    name === null ||
    (kind !== 'unit' && kind !== 'room') ||
    availability === null ||
    blockReason === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    property_id: propertyId,
    building_id: buildingId,
    floor_id: floorId,
    name,
    kind,
    availability,
    block_reason: blockReason,
  }
}

function parseBed(value: unknown): BedRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const spaceId = text(value, 'space_id')
  const name = text(value, 'name')
  const availability = parseAvailability(text(value, 'availability'))
  const blockReason = parseBlock(text(value, 'block_reason'))
  if (
    id === null ||
    spaceId === null ||
    name === null ||
    availability === null ||
    blockReason === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    space_id: spaceId,
    name,
    availability,
    block_reason: blockReason,
  }
}

async function readList<T>(
  response: Response,
  parse: (value: unknown) => T,
): Promise<T[]> {
  const body = await readBody(response)
  return pageItems(body).map(parse)
}

export async function listProperties(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<PropertyRecord[]> {
  const response = await request('/api/v1/properties/', { workspaceId, signal })
  return readList(response, parseProperty)
}

export async function createProperty(
  workspaceId: string,
  input: { name: string; address: string },
): Promise<PropertyRecord> {
  const response = await request('/api/v1/properties/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseProperty(await readBody(response))
}

export async function deleteProperty(
  workspaceId: string,
  propertyId: string,
): Promise<void> {
  const response = await request(`/api/v1/properties/${propertyId}/`, {
    method: 'DELETE',
    workspaceId,
  })
  if (!response.ok && response.status !== 204) {
    throw await errorFromResponse(response)
  }
}

export async function listBuildings(
  workspaceId: string,
  propertyId: string,
  signal?: AbortSignal,
): Promise<BuildingRecord[]> {
  const response = await request(
    `/api/v1/buildings/?property_id=${encodeURIComponent(propertyId)}`,
    { workspaceId, signal },
  )
  return readList(response, parseBuilding)
}

export async function createBuilding(
  workspaceId: string,
  input: { property_id: string; name: string },
): Promise<BuildingRecord> {
  const response = await request('/api/v1/buildings/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseBuilding(await readBody(response))
}

export async function listFloors(
  workspaceId: string,
  propertyId: string,
  signal?: AbortSignal,
): Promise<FloorRecord[]> {
  const response = await request(
    `/api/v1/floors/?property_id=${encodeURIComponent(propertyId)}`,
    { workspaceId, signal },
  )
  return readList(response, parseFloor)
}

export async function createFloor(
  workspaceId: string,
  input: { property_id: string; building_id?: string; name: string },
): Promise<FloorRecord> {
  const response = await request('/api/v1/floors/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseFloor(await readBody(response))
}

export async function listSpaces(
  workspaceId: string,
  propertyId: string,
  signal?: AbortSignal,
): Promise<SpaceRecord[]> {
  const response = await request(
    `/api/v1/spaces/?property_id=${encodeURIComponent(propertyId)}`,
    { workspaceId, signal },
  )
  return readList(response, parseSpace)
}

export async function createSpace(
  workspaceId: string,
  input: {
    property_id: string
    building_id?: string
    floor_id?: string
    name: string
    kind: SpaceKind
  },
): Promise<SpaceRecord> {
  const response = await request('/api/v1/spaces/', {
    method: 'POST',
    workspaceId,
    body: {
      ...input,
      availability: 'active',
      block_reason: '',
    },
  })
  return parseSpace(await readBody(response))
}

export async function updateSpaceAvailability(
  workspaceId: string,
  spaceId: string,
  input: { availability: Availability; block_reason: BlockReason },
): Promise<SpaceRecord> {
  const response = await request(`/api/v1/spaces/${spaceId}/`, {
    method: 'PATCH',
    workspaceId,
    body: input,
  })
  return parseSpace(await readBody(response))
}

export async function deleteSpace(
  workspaceId: string,
  spaceId: string,
): Promise<void> {
  const response = await request(`/api/v1/spaces/${spaceId}/`, {
    method: 'DELETE',
    workspaceId,
  })
  if (!response.ok && response.status !== 204) {
    throw await errorFromResponse(response)
  }
}

export async function listBeds(
  workspaceId: string,
  spaceId: string,
  signal?: AbortSignal,
): Promise<BedRecord[]> {
  const response = await request(
    `/api/v1/beds/?space_id=${encodeURIComponent(spaceId)}`,
    { workspaceId, signal },
  )
  return readList(response, parseBed)
}

export async function createBed(
  workspaceId: string,
  input: { space_id: string; name: string },
): Promise<BedRecord> {
  const response = await request('/api/v1/beds/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseBed(await readBody(response))
}

export async function updateBedAvailability(
  workspaceId: string,
  bedId: string,
  input: { availability: Availability; block_reason: BlockReason },
): Promise<BedRecord> {
  const response = await request(`/api/v1/beds/${bedId}/`, {
    method: 'PATCH',
    workspaceId,
    body: input,
  })
  return parseBed(await readBody(response))
}

export async function deleteBed(
  workspaceId: string,
  bedId: string,
): Promise<void> {
  const response = await request(`/api/v1/beds/${bedId}/`, {
    method: 'DELETE',
    workspaceId,
  })
  if (!response.ok && response.status !== 204) {
    throw await errorFromResponse(response)
  }
}
