"use client"

import Link from "next/link"

import type { CameraStatus, DeviceRecord, GatewayStatus } from "@/lib/iot/types"
import { formatDuration } from "@/lib/utils"
import { usePoll } from "@/hooks/use-device-api"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Icons } from "@/components/icons"

export function DeviceCard({ device }: { device: DeviceRecord }) {
  const { data, error, loading } = usePoll<GatewayStatus | CameraStatus>(`/api/devices/${device.id}/status`, 10000)
  const Icon = device.kind === "gateway" ? Icons.gateway : Icons.camera
  return (
    <Link href={`/dashboard/devices/${device.id}`} className="block">
      <Card className="h-full transition-colors hover:border-primary">
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Icon className="h-4 w-4" /> {device.id}
            </CardTitle>
            <p className="text-sm text-muted-foreground">{device.name}</p>
          </div>
          {loading ? (
            <Badge variant="outline">checking</Badge>
          ) : error ? (
            <Badge variant="destructive">offline</Badge>
          ) : (
            <Badge variant="success">online</Badge>
          )}
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p className="text-muted-foreground">
            {device.door ?? "no door"}, {device.baseUrl}
          </p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          {data && "door" in data && (
            <p>
              Door <strong>{data.door}</strong>, {data.grants} grants, {data.denials} denials, up {formatDuration(data.uptime)}
            </p>
          )}
          {data && "fps" in data && (
            <p>
              {data.fps.toFixed(1)} fps, {data.events} events, up {formatDuration(data.uptime)}
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}
