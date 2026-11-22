import "server-only"

import { db } from "@/lib/db"
import { env } from "@/lib/env"
import type { Decision, Integrity, PdpHealth, Source, Sourced } from "@/lib/types"

export const OPS_MODEL = "smartgate-ops"

async function pdpFetch(path: string, init: RequestInit = {}, timeoutMs = env.pdpTimeoutMs) {
  const headers = new Headers(init.headers)
  if (env.pdpToken) headers.set("Authorization", `Bearer ${env.pdpToken}`)
  const res = await fetch(`${env.pdpUrl}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!res.ok) throw new Error(`PDP ${path} answered HTTP ${res.status}`)
  return res.json()
}

function fallbackSource(): Source {
  return env.pdpUrl ? "offline" : "sample"
}

function describe(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

// ------------------------------------------------------------------ decisions

function sampleToDecision(row: Awaited<ReturnType<typeof db.decisionSample.findMany>>[number]): Decision {
  return {
    decision_id: row.id,
    txn: row.txn,
    door: row.door,
    uid: row.uid,
    subject_id: row.subjectId,
    effect: row.effect as Decision["effect"],
    code: row.code,
    stages: JSON.parse(row.stages),
    matched_rules: JSON.parse(row.matched),
    risk: JSON.parse(row.risk),
    agent: row.agent ? JSON.parse(row.agent) : null,
    decided_at: row.decidedAt.toISOString(),
    latency_ms: row.latencyMs,
  }
}

export async function listDecisions(
  opts: { limit?: number; door?: string; uid?: string } = {}
): Promise<Sourced<Decision[]>> {
  const limit = Math.min(Math.max(opts.limit ?? 50, 1), 500)
  if (env.pdpUrl) {
    try {
      const q = new URLSearchParams({ limit: String(limit) })
      if (opts.door) q.set("door", opts.door)
      if (opts.uid) q.set("uid", opts.uid)
      const live: Decision[] = await pdpFetch(`/pdp/decisions?${q}`)
      // A fresh PDP has an empty log: show the samples instead of empty charts, and say so.
      if (live.length === 0 && !opts.door && !opts.uid) {
        return { ...(await sampleDecisions(limit, opts)), source: "empty" }
      }
      return { data: live, source: "live" }
    } catch (error) {
      return { ...(await sampleDecisions(limit, opts)), source: "offline", error: describe(error) }
    }
  }
  return sampleDecisions(limit, opts)
}

async function sampleDecisions(limit: number, opts: { door?: string; uid?: string }): Promise<Sourced<Decision[]>> {
  const rows = await db.decisionSample.findMany({
    where: { door: opts.door || undefined, uid: opts.uid || undefined },
    orderBy: { decidedAt: "desc" },
    take: limit,
  })
  return { data: rows.map(sampleToDecision), source: fallbackSource() }
}

export async function getDecision(id: string): Promise<Decision | null> {
  if (env.pdpUrl) {
    try {
      return await pdpFetch(`/pdp/decisions/${encodeURIComponent(id)}`)
    } catch {
      // fall through to the samples
    }
  }
  const row = await db.decisionSample.findUnique({ where: { id } })
  return row ? sampleToDecision(row) : null
}

export async function getHealth(): Promise<Sourced<PdpHealth>> {
  if (!env.pdpUrl) return { data: { status: "not configured" }, source: "sample" }
  try {
    return { data: await pdpFetch("/health"), source: "live" }
  } catch (error) {
    return { data: { status: "unreachable" }, source: "offline", error: describe(error) }
  }
}

export async function getIntegrity(): Promise<Sourced<Integrity>> {
  if (env.pdpUrl) {
    try {
      return { data: await pdpFetch("/pdp/integrity"), source: "live" }
    } catch (error) {
      return { data: { ok: false, records: 0 }, source: "offline", error: describe(error) }
    }
  }
  return { data: { ok: true, records: await db.decisionSample.count() }, source: "sample" }
}

// ------------------------------------------------------------------ assistant

export type ChatTurn = { role: "user" | "assistant"; content: string }

/** Sends the conversation to the operations crew; answers offline when the PDP cannot. */
export async function askAssistant(history: ChatTurn[]): Promise<{ content: string; mode: "live" | "offline" }> {
  const question = history.filter((t) => t.role === "user").at(-1)?.content ?? ""
  if (env.pdpUrl) {
    try {
      const body = await pdpFetch(
        "/v1/chat/completions",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: OPS_MODEL, messages: history, stream: false }),
        },
        env.chatTimeoutMs
      )
      const content = body?.choices?.[0]?.message?.content
      if (typeof content === "string" && content.trim()) return { content, mode: "live" }
      throw new Error("empty answer")
    } catch (error) {
      return { content: await offlineAnswer(question, describe(error)), mode: "offline" }
    }
  }
  return { content: await offlineAnswer(question), mode: "offline" }
}

/** Rule-based answers from local data, so demos work without the PDP or an LLM key. */
async function offlineAnswer(question: string, error?: string): Promise<string> {
  const q = question.toLowerCase()
  const note = error
    ? `_The PDP could not be reached (${error}); this answer comes from the offline assistant._`
    : "_No PDP is configured (`LLM_ACCESS_API_URL`); this answer comes from the offline assistant using sample data._"
  const { data: recent } = await listDecisions({ limit: 200 })

  if (/(deny|denied|refus|reject)/.test(q)) {
    const denies = recent.filter((d) => d.effect === "deny")
    const byCode = countBy(denies, (d) => d.code)
    return [
      `**${denies.length} of the last ${recent.length} decisions were denials.**`,
      "",
      ...Object.entries(byCode).map(([code, n]) => `- \`${code}\`: ${n}`),
      "",
      note,
    ].join("\n")
  }
  if (/(door|gateway|device|node|camera|offline|status)/.test(q)) {
    const devices = await db.device.findMany({ orderBy: { id: "asc" } })
    return [
      `**${devices.length} edge nodes are registered.**`,
      "",
      ...devices.map((d) => `- **${d.id}** (${d.kind}) at ${d.door ?? "no door"}: ${d.baseUrl}`),
      "",
      "Administrators can see live status, events and recordings under **IoT devices**.",
      "",
      note,
    ].join("\n")
  }
  if (/(permit|grant|allow|access|summary|today|how many)/.test(q)) {
    const permits = recent.filter((d) => d.effect === "permit").length
    const byDoor = countBy(recent, (d) => d.door)
    return [
      `**Last ${recent.length} decisions:** ${permits} permits, ${recent.length - permits} denials.`,
      "",
      ...Object.entries(byDoor).map(([door, n]) => `- ${door}: ${n} requests`),
      "",
      note,
    ].join("\n")
  }
  return [
    "I am the operations assistant. With the PDP connected I turn an intent into a verified, audited change,",
    "for example *\"Sync the offline cache of door-1 and raise its PDP timeout to 25 s\"*.",
    "",
    "Offline, I can summarise **denials**, **access decisions** and **device status** from local data.",
    "",
    note,
  ].join("\n")
}

function countBy<T>(items: T[], key: (item: T) => string) {
  return items.reduce<Record<string, number>>((acc, item) => {
    acc[key(item)] = (acc[key(item)] ?? 0) + 1
    return acc
  }, {})
}
