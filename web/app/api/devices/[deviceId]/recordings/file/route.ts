import { cameraApi, safeDavPath } from "@/lib/iot"
import { binaryResponse, deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

/** Streams one file from the recorder's WebDAV share. `download=1` saves it instead of showing it. */
export const GET = deviceRoute(async ({ device, req }) => {
  const q = new URL(req.url).searchParams
  const path = safeDavPath(q.get("path"))
  const file = await cameraApi(device).davFile(path)
  const name = path.split("/").at(-1) ?? "recording"
  return binaryResponse(file.contentType, file.body, {
    "Content-Disposition": `${q.get("download") ? "attachment" : "inline"}; filename="${name}"`,
  })
})
