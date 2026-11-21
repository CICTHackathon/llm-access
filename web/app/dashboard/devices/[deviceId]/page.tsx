import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { db } from "@/lib/db"
import { iotMode } from "@/lib/iot"
import { requirePage } from "@/lib/session"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { CameraConsole } from "@/components/devices/camera-console"
import { DeleteDevice } from "@/components/devices/delete-device"
import { DeviceForm } from "@/components/devices/device-form"
import { GatewayConsole } from "@/components/devices/gateway-console"
import { NativeConsole } from "@/components/devices/native-console"
import { Icons } from "@/components/icons"
import { Shell } from "@/components/layout/shell"

export async function generateMetadata({ params }: { params: { deviceId: string } }): Promise<Metadata> {
  return { title: params.deviceId }
}

export default async function DevicePage({ params }: { params: { deviceId: string } }) {
  await requirePage("manageIot")
  const device = await db.device.findUnique({ where: { id: params.deviceId } })
  if (!device) notFound()
  const tokenMissing = iotMode === "live" && device.kind === "gateway" && (!device.tokenEnv || !process.env[device.tokenEnv])

  return (
    <Shell>
      <div className="flex flex-col gap-4 px-2 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <Link href="/dashboard/devices" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "-ml-3")}>
            <Icons.back className="mr-1 h-4 w-4" /> All devices
          </Link>
          <h1 className="flex items-center gap-2 text-2xl font-bold md:text-3xl">
            {device.kind === "gateway" ? <Icons.gateway className="h-6 w-6" /> : <Icons.camera className="h-6 w-6" />}
            {device.id}
            <Badge variant="outline">{device.kind}</Badge>
            {iotMode === "mock" && <Badge variant="secondary">simulated</Badge>}
          </h1>
          <p className="text-muted-foreground">
            {device.name}
            {device.door && `, ${device.door}`}
            {device.zone && ` (${device.zone})`}, {device.baseUrl}
          </p>
          {device.notes && <p className="text-sm text-muted-foreground">{device.notes}</p>}
          {tokenMissing && (
            <p className="text-sm text-destructive">
              No API token: set {device.tokenEnv ?? "a token variable"} on the web server, or the gateway answers 401.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <DeviceForm device={device} />
          <DeleteDevice deviceId={device.id} />
        </div>
      </div>

      {device.kind === "gateway" ? (
        <GatewayConsole deviceId={device.id} />
      ) : (
        <CameraConsole deviceId={device.id} streamUrl={device.streamUrl} />
      )}
      <NativeConsole url={device.baseUrl} mock={iotMode === "mock"} />
    </Shell>
  )
}
