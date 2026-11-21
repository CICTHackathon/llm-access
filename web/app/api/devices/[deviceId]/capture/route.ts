import { cameraApi } from "@/lib/iot"
import { binaryResponse, deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

/** One frame from the recorder's /capture, proxied so the browser never talks to the node. */
export const GET = deviceRoute(async ({ device }) => {
  const frame = await cameraApi(device).capture()
  return binaryResponse(frame.contentType, frame.body)
})
