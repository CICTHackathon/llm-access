import "server-only"

import { env } from "@/lib/env"

import type { Binary, CameraApi, DavEntry, DeviceRecord, GatewayApi } from "./types"

/** Errors from a node, carrying the HTTP status to return to the browser. */
export class DeviceError extends Error {
  constructor(message: string, readonly status = 502) {
    super(message)
  }
}

function client(device: DeviceRecord) {
  const base = device.baseUrl.replace(/\/+$/, "")
  const token = device.tokenEnv ? process.env[device.tokenEnv] ?? "" : ""

  async function call(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers)
    if (token) headers.set("X-Api-Token", token)
    let res: Response
    try {
      res = await fetch(`${base}${path}`, {
        ...init,
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(env.deviceTimeoutMs),
      })
    } catch (error) {
      throw new DeviceError(`${device.id} is unreachable at ${base} (${(error as Error).message})`, 504)
    }
    if (res.status === 401) {
      throw new DeviceError(
        `${device.id} rejected the API token${device.tokenEnv ? ` (check ${device.tokenEnv})` : ""}`,
        502
      )
    }
    if (!res.ok) throw new DeviceError(`${device.id} answered HTTP ${res.status} for ${path}`, 502)
    return res
  }

  const json = async <T>(path: string, init?: RequestInit) => (await call(path, init)).json() as Promise<T>
  const post = (path: string, body?: unknown) =>
    call(path, {
      method: "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  const binary = async (path: string): Promise<Binary> => {
    const res = await call(path)
    return { contentType: res.headers.get("content-type") ?? "application/octet-stream", body: await res.arrayBuffer() }
  }
  return { call, json, post, binary }
}

export function liveGateway(device: DeviceRecord): GatewayApi {
  const c = client(device)
  return {
    status: () => c.json("/api/status"),
    events: (limit = 50) => c.json(`/api/events?limit=${limit}`),
    acl: () => c.json("/api/acl"),
    aclRemove: async (uid) => void (await c.post("/api/acl", { remove: uid })),
    aclClear: async () => void (await c.post("/api/acl", { clear: true })),
    config: () => c.json("/api/config"),
    setConfig: async (key, value) => void (await c.post("/api/config", { key, value })),
    unlock: async () => void (await c.post("/api/unlock")),
    lock: async () => void (await c.post("/api/lock")),
    enrolArm: async (ms) => void (await c.post(`/api/enrol?ms=${ms}`)),
    enrolResult: () => c.json("/api/enrol"),
    reboot: async () => void (await c.post("/api/reboot")),
  }
}

export function liveCamera(device: DeviceRecord): CameraApi {
  const c = client(device)
  return {
    status: () => c.json("/api/status"),
    events: () => c.json("/api/events"),
    config: () => c.json("/api/config"),
    setConfig: async (key, value) =>
      void (await c.post(`/api/config?${new URLSearchParams({ [key]: String(value) })}`)),
    label: async (id, label) => void (await c.post(`/api/label?id=${id}&label=${label}`)),
    capture: () => c.binary("/capture"),
    davList: async (path) => {
      const res = await c.call(`/dav${encodePath(path)}`, {
        method: "PROPFIND",
        headers: { Depth: "1", "Content-Type": "application/xml" },
      })
      return parseMultistatus(await res.text(), path)
    },
    davFile: (path) => c.binary(`/dav${encodePath(path)}`),
    davDelete: async (path) => void (await c.call(`/dav${encodePath(path)}`, { method: "DELETE" })),
    reboot: async () => void (await c.post("/api/reboot")),
  }
}

function encodePath(path: string) {
  return path.split("/").map(encodeURIComponent).join("/")
}

/** Reads a WebDAV PROPFIND (Depth: 1) reply; the first response is the folder itself. */
export function parseMultistatus(xml: string, folder: string): DavEntry[] {
  const entries: DavEntry[] = []
  const responses = xml.match(/<(?:\w+:)?response\b[\s\S]*?<\/(?:\w+:)?response>/gi) ?? []
  const self = folder.replace(/\/+$/, "")
  for (const block of responses) {
    const href = decodeURIComponent(tag(block, "href") ?? "")
    const rel = href.replace(/^.*?\/dav/, "").replace(/\/+$/, "") || "/"
    if (rel === (self || "/")) continue
    const isDir = /<(?:\w+:)?collection\s*\/?>/i.test(block)
    entries.push({
      name: rel.split("/").filter(Boolean).at(-1) ?? rel,
      path: rel,
      isDir,
      size: Number(tag(block, "getcontentlength") ?? 0),
      modified: tag(block, "getlastmodified"),
    })
  }
  return entries.sort((a, b) => Number(b.isDir) - Number(a.isDir) || b.name.localeCompare(a.name))
}

function tag(block: string, name: string): string | null {
  const m = block.match(new RegExp(`<(?:\\w+:)?${name}[^>]*>([\\s\\S]*?)<\\/(?:\\w+:)?${name}>`, "i"))
  return m ? m[1].trim() : null
}
