export type DeviceKind = "gateway" | "camera"

export type DeviceRecord = {
  id: string
  kind: string
  name: string
  door: string | null
  zone: string | null
  baseUrl: string
  streamUrl: string | null
  tokenEnv: string | null
  notes: string | null
}

/** GET /api/status on the enforcement node (firmware/gateway-esp32/web.cpp). */
export type GatewayStatus = {
  door: "locked" | "opening" | "open" | "closing"
  state: string
  txn: string
  uid: string
  pinDigits: number
  attempts: number
  angle: number
  holdMs: number
  clockSet: boolean
  transactions: number
  grants: number
  denials: number
  degraded: number
  pdp: { configured: boolean; url: string; lastCode: number; lastMs: number }
  acl: number
  auditLast: number
  lcd: boolean
  enrolArmed: boolean
  ip: string
  rssi: number
  uptime: number
  epoch: number
  heap: number
  doorId: string
  signedDecisions: boolean
}

export type GatewayEvent = {
  id: number
  txn: string
  epoch: number
  uptime: number
  uid: string
  state: string
  effect: string
  reason: string
  pin: boolean
  unsigned: boolean
  note: string
}

export type AclEntry = { uid: string; pin: boolean; ttl: number }

/** GET /api/status on the recorder (firmware/esp32cam/web.cpp). */
export type CameraStatus = {
  ip: string
  uptime: number
  epoch: number
  clockSet: boolean
  fps: number
  frames: number
  events: number
  eventOpen: boolean
  area: number
  s1: number
  s2: number
  decodeMs: number
  analyseMs: number
  mlMs: number
  heap: number
  psram: number
  store: string
  storeUsed: number
  storeTotal: number
}

export type CameraEvent = {
  id: number
  time: string
  epoch: number
  verdict: string
  mlLabel: string
  s1: number
  s2: number
  frames: number
  label: number
  path: string
}

export type DavEntry = { name: string; path: string; isDir: boolean; size: number; modified: string | null }

export type Binary = { contentType: string; body: ArrayBuffer }

export interface GatewayApi {
  status(): Promise<GatewayStatus>
  events(limit?: number): Promise<{ last: number; events: GatewayEvent[] }>
  acl(): Promise<{ entries: AclEntry[]; capacity: number }>
  aclRemove(uid: string): Promise<void>
  aclClear(): Promise<void>
  config(): Promise<Record<string, unknown>>
  setConfig(key: string, value: string | number | boolean): Promise<void>
  unlock(): Promise<void>
  lock(): Promise<void>
  enrolArm(ms: number): Promise<void>
  enrolResult(): Promise<{ armed: boolean; uid: string }>
  reboot(): Promise<void>
}

export interface CameraApi {
  status(): Promise<CameraStatus>
  events(): Promise<CameraEvent[]>
  config(): Promise<Record<string, unknown>>
  setConfig(key: string, value: string | number | boolean): Promise<void>
  label(id: number, label: 0 | 1): Promise<void>
  capture(): Promise<Binary>
  davList(path: string): Promise<DavEntry[]>
  davFile(path: string): Promise<Binary>
  davDelete(path: string): Promise<void>
  reboot(): Promise<void>
}
