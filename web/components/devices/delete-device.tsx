"use client"

import { useRouter } from "next/navigation"

import { send } from "@/hooks/use-device-api"
import { toast } from "@/components/ui/use-toast"
import { ConfirmAction } from "@/components/devices/confirm-action"

export function DeleteDevice({ deviceId }: { deviceId: string }) {
  const router = useRouter()
  return (
    <ConfirmAction
      label="Remove"
      title={`Remove ${deviceId}?`}
      description="The device disappears from this interface. The node itself keeps running; nothing is sent to it."
      variant="destructive"
      onConfirm={async () => {
        try {
          await send(`/api/devices/${deviceId}`, "DELETE")
          toast({ title: `${deviceId} removed` })
          router.push("/dashboard/devices")
          router.refresh()
        } catch (e) {
          toast({ title: "Not removed", description: (e as Error).message, variant: "destructive" })
        }
      }}
    />
  )
}
