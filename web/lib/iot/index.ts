import "server-only"

import { db } from "@/lib/db"
import { env } from "@/lib/env"

import { DeviceError, liveCamera, liveGateway } from "./live"
import { mockCamera, mockGateway } from "./mock"
import type { CameraApi, DeviceRecord, GatewayApi } from "./types"

export { DeviceError }
export const iotMode = env.iotMode

/** Settings that are provisioned out of band (`llm-access provision`) and never written from the web. */
export const SECRET_SETTINGS = new Set(["apiToken", "pdpToken", "decisionKey"])

export async function findDevice(id: string): Promise<DeviceRecord> {
  const device = await db.device.findUnique({ where: { id } })
  if (!device) throw new DeviceError(`no device ${id}`, 404)
  return device
}

export function gatewayApi(device: DeviceRecord): GatewayApi {
  if (device.kind !== "gateway") throw new DeviceError(`${device.id} is not a gateway`, 400)
  return env.iotMode === "live" ? liveGateway(device) : mockGateway(device)
}

export function cameraApi(device: DeviceRecord): CameraApi {
  if (device.kind !== "camera") throw new DeviceError(`${device.id} is not a camera`, 400)
  return env.iotMode === "live" ? liveCamera(device) : mockCamera(device)
}

/** Replaces secret values with a marker, so tokens never reach the browser. */
export function maskSecrets(config: Record<string, unknown>) {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(config)) {
    out[key] = SECRET_SETTINGS.has(key) ? (value ? "set" : "not set") : value
  }
  return out
}

/** Folder paths under the WebDAV share: no traversal, no odd characters. */
export function safeDavPath(raw: string | null): string {
  const path = `/${(raw ?? "/").replace(/^\/+/, "")}`.replace(/\/+$/, "") || "/"
  if (path.split("/").some((part) => part === ".." || part === ".")) throw new DeviceError("invalid path", 400)
  if (!/^[A-Za-z0-9_./-]*$/.test(path)) throw new DeviceError("invalid path", 400)
  return path
}

/** Turns any thrown error into a JSON response body and status. */
export function deviceErrorResponse(error: unknown) {
  if (error instanceof DeviceError) return { body: { error: error.message }, status: error.status }
  console.error(error)
  return { body: { error: "Unexpected error talking to the device" }, status: 500 }
}
