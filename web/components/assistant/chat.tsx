"use client"

import * as React from "react"

import { cn, formatDateTime } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/use-toast"
import { Icons } from "@/components/icons"
import { Markdown } from "@/components/markdown"

type ThreadSummary = { id: string; title: string; updatedAt: string }
type Message = { id: string; role: string; content: string; mode: string; createdAt: string }

const SUGGESTIONS = [
  "Why were requests denied this week?",
  "Show the status of the doors and gateways",
  "Sync the offline cache of door-1 and raise its PDP timeout to 25 s",
  "Run a compliance check on every node",
]

export function Chat({ initialThreads, pdpMode }: { initialThreads: ThreadSummary[]; pdpMode: "live" | "offline" }) {
  const [threads, setThreads] = React.useState(initialThreads)
  const [active, setActive] = React.useState<string | null>(initialThreads[0]?.id ?? null)
  const [messages, setMessages] = React.useState<Message[]>([])
  const [input, setInput] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const bottom = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (!active) return setMessages([])
    let cancelled = false
    fetch(`/api/threads/${active}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("could not load the conversation"))))
      .then((t) => !cancelled && setMessages(t.messages))
      .catch((e) => toast({ title: "Error", description: e.message, variant: "destructive" }))
    return () => {
      cancelled = true
    }
  }, [active])

  React.useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages, busy])

  async function send(text: string) {
    const message = text.trim()
    if (!message || busy) return
    setBusy(true)
    setInput("")
    const pending: Message = { id: `pending-${Date.now()}`, role: "user", content: message, mode: "live", createdAt: new Date().toISOString() }
    setMessages((m) => [...m, pending])
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId: active ?? undefined, message }),
      })
      const body = await res.json()
      if (!res.ok) throw new Error(body.error ?? "The assistant did not answer")
      setMessages((m) => [...m, body.message])
      if (!active) {
        setActive(body.threadId)
        setThreads((t) => [{ id: body.threadId, title: body.title, updatedAt: new Date().toISOString() }, ...t])
      } else {
        setThreads((t) => {
          const current = t.find((x) => x.id === active)
          return current ? [{ ...current, updatedAt: new Date().toISOString() }, ...t.filter((x) => x.id !== active)] : t
        })
      }
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== pending.id))
      setInput(message)
      toast({ title: "Message not sent", description: (e as Error).message, variant: "destructive" })
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string) {
    const res = await fetch(`/api/threads/${id}`, { method: "DELETE" })
    if (!res.ok) return toast({ title: "Could not delete the conversation", variant: "destructive" })
    setThreads((t) => t.filter((x) => x.id !== id))
    if (active === id) setActive(null)
  }

  return (
    <div className="grid min-h-[600px] gap-4 md:grid-cols-[240px_1fr]">
      <aside className="flex flex-col gap-2 rounded-lg border p-2">
        <Button variant="outline" size="sm" onClick={() => setActive(null)}>
          <Icons.add className="mr-2 h-4 w-4" />
          New conversation
        </Button>
        <ScrollArea className="h-[540px]">
          <ul className="space-y-1">
            {threads.map((t) => (
              <li key={t.id} className="group flex items-center gap-1">
                <button
                  onClick={() => setActive(t.id)}
                  className={cn(
                    "flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent",
                    active === t.id && "bg-accent font-medium"
                  )}
                  title={t.title}
                >
                  {t.title}
                </button>
                <button
                  onClick={() => remove(t.id)}
                  className="rounded p-1 text-muted-foreground opacity-0 hover:text-destructive group-hover:opacity-100"
                  aria-label={`Delete ${t.title}`}
                >
                  <Icons.trash className="h-4 w-4" />
                </button>
              </li>
            ))}
            {threads.length === 0 && <li className="px-2 py-4 text-sm text-muted-foreground">No conversations yet.</li>}
          </ul>
        </ScrollArea>
      </aside>

      <section className="flex flex-col rounded-lg border">
        <div className="flex items-center justify-between border-b px-4 py-2 text-sm">
          <span className="font-medium">Operations assistant</span>
          <Badge variant={pdpMode === "live" ? "success" : "secondary"}>
            {pdpMode === "live" ? "connected to the PDP" : "offline assistant"}
          </Badge>
        </div>
        <ScrollArea className="h-[460px] px-4">
          <div className="space-y-4 py-4">
            {messages.length === 0 && !busy && (
              <div className="space-y-3 py-6 text-center">
                <Icons.chat className="mx-auto h-10 w-10 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Describe what you want in plain language. The crew plans, verifies, deploys and audits the change.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <Button key={s} variant="outline" size="sm" onClick={() => send(s)}>
                      {s}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[85%] rounded-lg px-3 py-2",
                    m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                  )}
                >
                  {m.role === "user" ? <p className="whitespace-pre-wrap text-sm">{m.content}</p> : <Markdown text={m.content} />}
                  <p className={cn("mt-1 text-[11px] opacity-70")}>
                    {formatDateTime(m.createdAt)}
                    {m.role !== "user" && m.mode === "offline" && " (offline assistant)"}
                  </p>
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Icons.spinner className="h-4 w-4 animate-spin" />
                The crew is working on it. A live run can take a minute.
              </div>
            )}
            <div ref={bottom} />
          </div>
        </ScrollArea>
        <form
          className="flex gap-2 border-t p-3"
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Ask the assistant, e.g. raise the PDP timeout of gw-1 to 25 s"
            className="min-h-[44px] resize-none"
            rows={2}
            disabled={busy}
          />
          <Button type="submit" disabled={busy || !input.trim()} aria-label="Send">
            <Icons.send className="h-4 w-4" />
          </Button>
        </form>
      </section>
    </div>
  )
}
