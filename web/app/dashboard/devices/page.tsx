import type { Metadata } from "next"

import { db } from "@/lib/db"
import { iotMode } from "@/lib/iot"
import { requirePage } from "@/lib/session"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { DeviceCard } from "@/components/devices/device-card"
import { DeviceForm } from "@/components/devices/device-form"
import { EmptyPlaceholder } from "@/components/empty-placeholder"
import { Icons } from "@/components/icons"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"

export const metadata: Metadata = { title: "IoT devices" }

export default async function DevicesPage() {
  await requirePage("manageIot")
  const devices = await db.device.findMany({ orderBy: [{ door: "asc" }, { id: "asc" }] })
  const gateways = devices.filter((d) => d.kind === "gateway")
  const cameras = devices.filter((d) => d.kind === "camera")

  return (
    <Shell>
      <DashboardHeader heading="IoT devices" text="Every gateway console and camera share, in one place. Administrators only.">
        <DeviceForm />
      </DashboardHeader>
      {iotMode === "mock" && (
        <Alert>
          <Icons.warning className="h-4 w-4" />
          <AlertTitle>Simulated devices</AlertTitle>
          <AlertDescription>
            IOT_MODE is &quot;mock&quot;: the nodes are simulated from the seeded decisions. Set IOT_MODE=live and the gateway
            token variables to manage the real ESP32 nodes.
          </AlertDescription>
        </Alert>
      )}
      {devices.length === 0 ? (
        <EmptyPlaceholder>
          <Icons.devices className="h-10 w-10 text-muted-foreground" />
          <EmptyPlaceholder.Title>No devices yet</EmptyPlaceholder.Title>
          <EmptyPlaceholder.Description>Add the gateways and cameras listed in config/inventory.yaml.</EmptyPlaceholder.Description>
          <DeviceForm />
        </EmptyPlaceholder>
      ) : (
        <>
          <section className="space-y-3">
            <h2 className="px-2 text-lg font-semibold">Gateways (enforcement points)</h2>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {gateways.map((d) => (
                <DeviceCard key={d.id} device={d} />
              ))}
            </div>
          </section>
          <section className="space-y-3">
            <h2 className="px-2 text-lg font-semibold">Cameras (movement recorders)</h2>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {cameras.map((d) => (
                <DeviceCard key={d.id} device={d} />
              ))}
            </div>
          </section>
        </>
      )}
    </Shell>
  )
}
