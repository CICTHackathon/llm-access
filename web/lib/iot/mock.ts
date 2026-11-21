import "server-only"

import { db } from "@/lib/db"

import { DeviceError } from "./live"
import type {
  AclEntry,
  Binary,
  CameraApi,
  CameraEvent,
  DavEntry,
  DeviceRecord,
  GatewayApi,
  GatewayEvent,
} from "./types"

// Simulated nodes for demos without hardware. The state lives in memory, starts from
// the seeded decisions at the node's door, and reacts to the same calls as the firmware.

type GatewayState = {
  door: "locked" | "open"
  openedAt: number
  config: Record<string, unknown>
  acl: AclEntry[]
  events: GatewayEvent[]
  enrol: { armedUntil: number; uid: string }
  bootedAt: number
}

type CameraState = {
  config: Record<string, unknown>
  events: CameraEvent[]
  files: Map<string, { size: number; modified: Date; body: string; type: string }>
  bootedAt: number
}

declare global {
  // eslint-disable-next-line no-var
  var iotMock: { gateways: Map<string, GatewayState>; cameras: Map<string, CameraState> } | undefined
}
const store = (global.iotMock ??= { gateways: new Map(), cameras: new Map() })

const now = () => Date.now()
const epoch = () => Math.floor(now() / 1000)
const OPEN_HOLD_MS = 4000

async function doorDecisions(door: string | null, take: number) {
  if (!door) return []
  return db.decisionSample.findMany({ where: { door }, orderBy: { decidedAt: "desc" }, take })
}

// ------------------------------------------------------------------ gateway

async function gatewayState(device: DeviceRecord): Promise<GatewayState> {
  const existing = store.gateways.get(device.id)
  if (existing) return existing
  const decisions = await doorDecisions(device.door, 40)
  const events: GatewayEvent[] = decisions.map((d, i) => ({
    id: decisions.length - i,
    txn: d.txn,
    epoch: Math.floor(d.decidedAt.getTime() / 1000),
    uptime: 0,
    uid: d.uid,
    state: d.effect === "permit" ? "GRANTED" : "DENIED",
    effect: d.effect,
    reason: d.code.slice(0, 23),
    pin: true,
    unsigned: false,
    note: "",
  }))
  const state: GatewayState = {
    door: "locked",
    openedAt: 0,
    bootedAt: now() - 3 * 86400_000 - 4 * 3600_000,
    config: {
      closedAngle: 0,
      openAngle: 90,
      openHoldMs: OPEN_HOLD_MS,
      pinTimeoutMs: 15000,
      pdpTimeoutMs: 20000,
      pinAttempts: 3,
      requirePin: true,
      degradedAllow: false,
      buzzerEnabled: true,
      pdpUrl: "http://192.168.1.10:8080/pdp/decide",
      doorId: device.door ?? device.id,
      pdpToken: "set",
      decisionKey: "set",
      apiToken: "set",
      pinMin: 4,
      pinMax: 8,
      lcd: "20x4",
    },
    acl: [
      { uid: "0xa1b2c3d4", pin: true, ttl: 3600 * 9 },
      { uid: "0xb2c3d4e5", pin: true, ttl: 3600 * 9 },
    ],
    events,
    enrol: { armedUntil: 0, uid: "" },
  }
  store.gateways.set(device.id, state)
  return state
}

function pushGatewayEvent(state: GatewayState, partial: Partial<GatewayEvent>) {
  const id = (state.events[0]?.id ?? 0) + 1
  state.events.unshift({
    id,
    txn: "",
    epoch: epoch(),
    uptime: Math.floor((now() - state.bootedAt) / 1000),
    uid: "",
    state: "IDLE",
    effect: "",
    reason: "",
    pin: false,
    unsigned: false,
    note: "",
    ...partial,
  })
  state.events = state.events.slice(0, 64)
}

export function mockGateway(device: DeviceRecord): GatewayApi {
  return {
    async status() {
      const s = await gatewayState(device)
      if (s.door === "open" && now() - s.openedAt > Number(s.config.openHoldMs)) s.door = "locked"
      const grants = s.events.filter((e) => e.effect === "permit").length
      const denials = s.events.filter((e) => e.effect === "deny").length
      return {
        door: s.door,
        state: s.door === "open" ? "OPEN" : s.enrol.armedUntil > now() ? "ENROL" : "IDLE",
        txn: "",
        uid: "",
        pinDigits: 0,
        attempts: 0,
        angle: s.door === "open" ? Number(s.config.openAngle) : Number(s.config.closedAngle),
        holdMs: s.door === "open" ? Math.max(0, Number(s.config.openHoldMs) - (now() - s.openedAt)) : 0,
        clockSet: true,
        transactions: grants + denials,
        grants,
        denials,
        degraded: 0,
        pdp: { configured: true, url: String(s.config.pdpUrl), lastCode: 200, lastMs: 184 },
        acl: s.acl.length,
        auditLast: s.events[0]?.id ?? 0,
        lcd: true,
        enrolArmed: s.enrol.armedUntil > now(),
        ip: new URL(device.baseUrl).hostname,
        rssi: -58 - (epoch() % 7),
        uptime: Math.floor((now() - s.bootedAt) / 1000),
        epoch: epoch(),
        heap: 182_000 - (epoch() % 900),
        doorId: String(s.config.doorId),
        signedDecisions: true,
      }
    },
    async events(limit = 50) {
      const s = await gatewayState(device)
      return { last: s.events[0]?.id ?? 0, events: s.events.slice(0, limit) }
    },
    async acl() {
      const s = await gatewayState(device)
      return { entries: s.acl, capacity: 32 }
    },
    async aclRemove(uid) {
      const s = await gatewayState(device)
      s.acl = s.acl.filter((e) => e.uid !== uid)
    },
    async aclClear() {
      ;(await gatewayState(device)).acl = []
    },
    async config() {
      return { ...(await gatewayState(device)).config }
    },
    async setConfig(key, value) {
      const s = await gatewayState(device)
      if (!(key in s.config)) throw new DeviceError(`unknown setting ${key}`, 400)
      s.config[key] = value
    },
    async unlock() {
      const s = await gatewayState(device)
      s.door = "open"
      s.openedAt = now()
      pushGatewayEvent(s, { state: "OPEN", effect: "permit", reason: "remote", note: "operator override" })
    },
    async lock() {
      const s = await gatewayState(device)
      s.door = "locked"
      pushGatewayEvent(s, { state: "IDLE", effect: "deny", reason: "remote", note: "operator lock" })
    },
    async enrolArm(ms) {
      const s = await gatewayState(device)
      s.enrol = { armedUntil: now() + ms, uid: "" }
      // A simulated card is presented a few seconds after arming.
      setTimeout(() => {
        if (s.enrol.armedUntil > now()) s.enrol = { armedUntil: 0, uid: "0x5e1f2a3b" }
      }, Math.min(ms, 3000))
    },
    async enrolResult() {
      const s = await gatewayState(device)
      const result = { armed: s.enrol.armedUntil > now(), uid: s.enrol.uid }
      if (result.uid) s.enrol.uid = ""
      return result
    },
    async reboot() {
      const s = await gatewayState(device)
      s.bootedAt = now()
      s.door = "locked"
    },
  }
}

// ------------------------------------------------------------------ camera

function frameSvg(title: string, subtitle: string, verdict?: string) {
  const colour = verdict === "person" ? "#2e7d32" : verdict ? "#b8860b" : "#3d6bb3"
  return `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9e4d8"/><stop offset="1" stop-color="#cfc7b6"/></linearGradient></defs>
  <rect width="640" height="480" fill="url(#g)"/>
  <rect x="120" y="60" width="400" height="400" fill="#b9c4cf" stroke="#7d8b99" stroke-width="10"/>
  <line x1="320" y1="60" x2="320" y2="460" stroke="#7d8b99" stroke-width="8"/>
  <rect x="300" y="250" width="12" height="60" rx="5" fill="#5a6672"/><rect x="328" y="250" width="12" height="60" rx="5" fill="#5a6672"/>
  <rect x="352" y="210" width="34" height="56" rx="4" fill="#222"/><circle cx="369" cy="226" r="6" fill="#3fa9f5"/>
  ${verdict ? `<rect x="200" y="120" width="160" height="320" fill="none" stroke="${colour}" stroke-width="4" stroke-dasharray="10 6"/>` : ""}
  <rect x="0" y="0" width="640" height="38" fill="rgba(0,0,0,0.55)"/>
  <text x="14" y="25" font-family="Helvetica, Arial" font-size="18" fill="#fff">${title}</text>
  <text x="626" y="25" font-family="Helvetica, Arial" font-size="15" fill="#ffd54f" text-anchor="end">SIMULATED</text>
  <text x="14" y="466" font-family="Helvetica, Arial" font-size="15" fill="#333">${subtitle}</text>
</svg>`
}

function stamp(d: Date) {
  const p = (n: number) => String(n).padStart(2, "0")
  return {
    day: `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`,
    time: `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`,
  }
}

async function cameraState(device: DeviceRecord): Promise<CameraState> {
  const existing = store.cameras.get(device.id)
  if (existing) return existing
  const decisions = await doorDecisions(device.door, 30)
  const files = new Map<string, { size: number; modified: Date; body: string; type: string }>()
  const events: CameraEvent[] = decisions.map((d, i) => {
    const id = 500 + decisions.length - i
    // Movement through the door after a grant; motion with no credential after some denials.
    const verdict = d.effect === "permit" || i % 4 === 0 ? "person" : "motion"
    const { day, time } = stamp(d.decidedAt)
    const path = `/events/${day}/${time}_${id}_${verdict}.svg`
    const body = frameSvg(`${device.id}  ${d.decidedAt.toLocaleString("en-GB")}`, `event ${id}: ${verdict}`, verdict)
    files.set(path, { size: body.length, modified: d.decidedAt, body, type: "image/svg+xml" })
    const sidecar = JSON.stringify(
      { id, epoch: Math.floor(d.decidedAt.getTime() / 1000), verdict, s1: 0.71, s2: verdict === "person" ? 0.88 : 0.34, box: [200, 120, 360, 440] },
      null,
      2
    )
    files.set(path.replace(/\.svg$/, ".json"), { size: sidecar.length, modified: d.decidedAt, body: sidecar, type: "application/json" })
    return {
      id,
      time: d.decidedAt.toISOString(),
      epoch: Math.floor(d.decidedAt.getTime() / 1000),
      verdict,
      mlLabel: verdict === "person" ? "person" : "other",
      s1: 0.71,
      s2: verdict === "person" ? 0.88 : 0.34,
      frames: 12 + (id % 9),
      label: -1,
      path: `/dav${path}`,
    }
  })
  const state: CameraState = {
    bootedAt: now() - 2 * 86400_000,
    events,
    files,
    config: { framesize: "VGA", quality: 12, threshold: 18, persistence: 3, minArea: 0.02, lamp: false, mlEnabled: true },
  }
  store.cameras.set(device.id, state)
  return state
}

function folderOf(path: string) {
  return path.split("/").slice(0, -1).join("/") || "/"
}

export function mockCamera(device: DeviceRecord): CameraApi {
  return {
    async status() {
      const s = await cameraState(device)
      const used = [...s.files.values()].reduce((n, f) => n + f.size, 0)
      return {
        ip: new URL(device.baseUrl).hostname,
        uptime: Math.floor((now() - s.bootedAt) / 1000),
        epoch: epoch(),
        clockSet: true,
        fps: 9.6,
        frames: Math.floor((now() - s.bootedAt) / 104),
        events: s.events.length,
        eventOpen: false,
        area: 0.004,
        s1: 0.12,
        s2: 0.08,
        decodeMs: 31,
        analyseMs: 9,
        mlMs: 46,
        heap: 96_000,
        psram: 3_900_000,
        store: "sd",
        storeUsed: used,
        storeTotal: 15_931_539_456,
      }
    },
    async events() {
      return (await cameraState(device)).events
    },
    async config() {
      return { ...(await cameraState(device)).config }
    },
    async setConfig(key, value) {
      const s = await cameraState(device)
      if (!(key in s.config)) throw new DeviceError(`unknown setting ${key}`, 400)
      s.config[key] = value
    },
    async label(id, label) {
      const s = await cameraState(device)
      const e = s.events.find((x) => x.id === id)
      if (!e) throw new DeviceError(`no event ${id}`, 404)
      e.label = label
    },
    async capture(): Promise<Binary> {
      const body = frameSvg(`${device.id}  ${new Date().toLocaleString("en-GB")}`, "live frame")
      return { contentType: "image/svg+xml", body: new TextEncoder().encode(body).buffer as ArrayBuffer }
    },
    async davList(path) {
      const s = await cameraState(device)
      const folder = path.replace(/\/+$/, "") || "/"
      const children = new Map<string, DavEntry>()
      for (const [filePath, f] of s.files) {
        if (!filePath.startsWith(folder === "/" ? "/" : `${folder}/`)) continue
        const rest = filePath.slice(folder === "/" ? 1 : folder.length + 1)
        const [head, ...tail] = rest.split("/")
        const childPath = `${folder === "/" ? "" : folder}/${head}`
        const isDir = tail.length > 0
        const prev = children.get(childPath)
        children.set(childPath, {
          name: head,
          path: childPath,
          isDir,
          size: (prev?.size ?? 0) + (isDir ? 0 : f.size),
          modified: f.modified.toUTCString(),
        })
      }
      if (!children.size && folder !== "/") throw new DeviceError(`no folder ${folder}`, 404)
      return [...children.values()].sort((a, b) => Number(b.isDir) - Number(a.isDir) || b.name.localeCompare(a.name))
    },
    async davFile(path) {
      const f = (await cameraState(device)).files.get(path)
      if (!f) throw new DeviceError(`no file ${path}`, 404)
      return { contentType: f.type, body: new TextEncoder().encode(f.body).buffer as ArrayBuffer }
    },
    async davDelete(path) {
      const s = await cameraState(device)
      const isFolder = ![...s.files.keys()].includes(path)
      let removed = 0
      for (const key of [...s.files.keys()]) {
        if (key === path || (isFolder && key.startsWith(`${path}/`))) {
          s.files.delete(key)
          removed++
        }
      }
      if (!removed) throw new DeviceError(`no file or folder ${path}`, 404)
      s.events = s.events.filter((e) => s.files.has(e.path.replace(/^\/dav/, "")) || folderOf(e.path) === "/")
    },
    async reboot() {
      ;(await cameraState(device)).bootedAt = now()
    },
  }
}
