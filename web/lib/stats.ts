import type { Decision } from "@/lib/types"

export type DayCount = { date: string; permit: number; deny: number }
export type CodeCount = { name: string; count: number; color: string }

const PALETTE = ["#dc2626", "#ea580c", "#d97706", "#7c3aed", "#2563eb", "#0891b2", "#db2777", "#4b5563"]

export function decisionStats(decisions: Decision[]) {
  const permits = decisions.filter((d) => d.effect === "permit")
  const denies = decisions.filter((d) => d.effect === "deny")
  const reviewed = decisions.filter((d) => d.agent)
  const tightened = decisions.filter((d) => d.agent?.effect === "deny")

  const byDay = new Map<string, DayCount>()
  for (const d of decisions) {
    const day = d.decided_at.slice(0, 10)
    const row = byDay.get(day) ?? { date: day, permit: 0, deny: 0 }
    row[d.effect] += 1
    byDay.set(day, row)
  }

  const codes = new Map<string, number>()
  for (const d of denies) codes.set(d.code, (codes.get(d.code) ?? 0) + 1)
  const denyCodes: CodeCount[] = [...codes.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([name, count], i) => ({ name, count, color: PALETTE[i % PALETTE.length] }))

  const latency = permits.length ? Math.round(permits.reduce((n, d) => n + d.latency_ms, 0) / permits.length) : 0

  return {
    total: decisions.length,
    permits: permits.length,
    denies: denies.length,
    denyRate: decisions.length ? Math.round((denies.length / decisions.length) * 100) : 0,
    reviewed: reviewed.length,
    tightened: tightened.length,
    avgPermitLatencyMs: latency,
    byDay: [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date)),
    denyCodes,
  }
}
