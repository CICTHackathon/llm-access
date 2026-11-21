"use client"

import * as React from "react"

/** Polls a device API route. `error` holds the message when the node does not answer. */
export function usePoll<T>(url: string | null, intervalMs = 0) {
  const [data, setData] = React.useState<T | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)

  const load = React.useCallback(async () => {
    if (!url) return
    try {
      const res = await fetch(url, { cache: "no-store" })
      const body = await res.json()
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`)
      setData(body)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [url])

  React.useEffect(() => {
    load()
    if (!intervalMs) return
    const timer = setInterval(load, intervalMs)
    return () => clearInterval(timer)
  }, [load, intervalMs])

  return { data, error, loading, reload: load }
}

/** POST/DELETE helper that throws the API's error message. */
export async function send(url: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (res.status === 204) return null
  const json = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(json.error ?? `HTTP ${res.status}`)
  return json
}
