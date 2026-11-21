"use client"

import * as React from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

/**
 * The console each node serves at "/" (iot-hardware console/index.html). It runs in the
 * browser and talks to the node directly, so it needs network access to the node and the
 * node's API token (entered in its Setup tab). The panels above go through this server instead.
 */
export function NativeConsole({ url, mock }: { url: string; mock: boolean }) {
  const [embedded, setEmbedded] = React.useState(false)
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
        <div>
          <CardTitle className="text-base">Device console</CardTitle>
          <CardDescription>
            The node&apos;s own operator page (Door, Camera, Timeline and Setup tabs). It connects from your browser straight to{" "}
            <code>{url}</code>, so it only works on the device network.
          </CardDescription>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="outline" onClick={() => setEmbedded((e) => !e)} disabled={mock}>
            {embedded ? "Hide" : "Embed"}
          </Button>
          <a href={url} target="_blank" rel="noreferrer">
            <Button size="sm" variant="outline" disabled={mock}>
              Open
            </Button>
          </a>
        </div>
      </CardHeader>
      {mock && (
        <CardContent className="text-sm text-muted-foreground">
          Not available while the devices are simulated (IOT_MODE=mock).
        </CardContent>
      )}
      {embedded && !mock && (
        <CardContent>
          <iframe src={url} title="Device console" className="h-[640px] w-full rounded-md border" sandbox="allow-scripts allow-same-origin allow-forms" />
        </CardContent>
      )}
    </Card>
  )
}
