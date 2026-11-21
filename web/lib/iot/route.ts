import "server-only"

import { NextResponse } from "next/server"

import { requireApi, type SessionUser } from "@/lib/session"

import { deviceErrorResponse, findDevice } from "./index"
import type { DeviceRecord } from "./types"

type Handler = (ctx: { user: SessionUser; device: DeviceRecord; req: Request }) => Promise<Response | unknown>

/** Admin-only device route: checks the role, loads the device, maps device errors to JSON. */
export function deviceRoute(handler: Handler) {
  return async (req: Request, { params }: { params: { deviceId: string } }) => {
    const { user, error } = await requireApi("manageIot")
    if (error) return error
    try {
      const device = await findDevice(params.deviceId)
      const result = await handler({ user, device, req })
      return result instanceof Response ? result : NextResponse.json(result ?? { ok: true })
    } catch (err) {
      const { body, status } = deviceErrorResponse(err)
      return NextResponse.json(body, { status })
    }
  }
}

export function binaryResponse(contentType: string, body: ArrayBuffer, extra: Record<string, string> = {}) {
  return new Response(body, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      // Bytes come from a device: never let them run script under this origin (e.g. an SVG).
      "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'; sandbox",
      ...extra,
    },
  })
}
