import { cameraApi, gatewayApi } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

export const GET = deviceRoute(async ({ device }) =>
  device.kind === "gateway" ? gatewayApi(device).status() : cameraApi(device).status()
)
