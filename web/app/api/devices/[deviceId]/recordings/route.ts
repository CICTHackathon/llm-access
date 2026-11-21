import { audit } from "@/lib/audit"
import { cameraApi, DeviceError, safeDavPath } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

/** Lists a folder of the recorder's WebDAV share (default: /events). */
export const GET = deviceRoute(async ({ device, req }) => {
  const path = safeDavPath(new URL(req.url).searchParams.get("path") ?? "/events")
  return { path, entries: await cameraApi(device).davList(path) }
})

/** Deletes a recording or a whole day folder. */
export const DELETE = deviceRoute(async ({ user, device, req }) => {
  const path = safeDavPath(new URL(req.url).searchParams.get("path"))
  if (path === "/" || path === "/events") throw new DeviceError("refusing to delete the whole share", 400)
  await cameraApi(device).davDelete(path)
  await audit(user, "recording.delete", `${device.id}:${path}`)
  return { ok: true }
})
