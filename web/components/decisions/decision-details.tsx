"use client"

import type { Decision } from "@/lib/types"
import { cn, formatDateTime } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Icons } from "@/components/icons"

export function EffectBadge({ effect }: { effect: Decision["effect"] }) {
  return <Badge variant={effect === "permit" ? "success" : "destructive"}>{effect}</Badge>
}

export function DecisionDetails({ decision }: { decision: Decision }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          Details
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <EffectBadge effect={decision.effect} /> <code>{decision.code}</code>
          </DialogTitle>
          <DialogDescription>
            {decision.door}, card {decision.uid}
            {decision.subject_id ? ` (${decision.subject_id})` : ""}, {formatDateTime(decision.decided_at)}, {decision.latency_ms} ms
          </DialogDescription>
        </DialogHeader>

        <section>
          <h3 className="mb-2 text-sm font-semibold">Pipeline</h3>
          <ol className="space-y-1.5">
            {decision.stages.map((s) => (
              <li key={s.name} className="flex items-center gap-2 text-sm">
                {s.passed ? (
                  <Icons.check className="h-4 w-4 text-emerald-600" />
                ) : (
                  <Icons.close className="h-4 w-4 text-red-600" />
                )}
                <span className="w-28 font-medium">{s.name}</span>
                <code className={cn("text-xs", !s.passed && "text-red-600")}>{s.code}</code>
              </li>
            ))}
          </ol>
        </section>

        {decision.matched_rules.length > 0 && (
          <section>
            <h3 className="mb-1 text-sm font-semibold">Matched rules</h3>
            <div className="flex flex-wrap gap-1">
              {decision.matched_rules.map((r) => (
                <Badge key={r} variant="outline">
                  {r}
                </Badge>
              ))}
            </div>
          </section>
        )}

        {decision.risk.length > 0 && (
          <section>
            <h3 className="mb-1 text-sm font-semibold">Risk signals</h3>
            <ul className="space-y-1 text-sm">
              {decision.risk.map((r) => (
                <li key={r.code}>
                  <Badge variant={r.severity === "critical" ? "destructive" : r.severity === "warn" ? "warning" : "secondary"}>
                    {r.severity}
                  </Badge>{" "}
                  <code>{r.code}</code>: {r.detail}
                </li>
              ))}
            </ul>
          </section>
        )}

        {decision.agent && (
          <section>
            <h3 className="mb-1 text-sm font-semibold">Agent review</h3>
            <p className="text-sm">
              <EffectBadge effect={decision.agent.effect} /> <code>{decision.agent.code}</code>, confidence{" "}
              {Math.round(decision.agent.confidence * 100)}%
            </p>
            <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
              {decision.agent.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            {decision.agent.cited_policies.length > 0 && (
              <p className="mt-1 text-xs text-muted-foreground">Cited: {decision.agent.cited_policies.join(", ")}</p>
            )}
          </section>
        )}

        <p className="text-xs text-muted-foreground">
          Decision <code>{decision.decision_id}</code>, transaction <code>{decision.txn}</code>
        </p>
      </DialogContent>
    </Dialog>
  )
}
