/** One access decision, in the PDP's decision-log format (src/mcp_server/engine/domain/access.py). */
export type Decision = {
  decision_id: string
  txn: string
  door: string
  uid: string
  subject_id: string | null
  effect: "permit" | "deny"
  code: string
  stages: { name: string; passed: boolean; code: string; detail?: string }[]
  matched_rules: string[]
  risk: { code: string; severity: "info" | "warn" | "critical"; detail: string }[]
  agent: {
    effect: "permit" | "deny"
    confidence: number
    code: string
    reasons: string[]
    cited_policies: string[]
  } | null
  decided_at: string
  latency_ms: number
}

/** Where data came from: the live PDP, or sample data because the PDP is off or unreachable. */
export type Source = "live" | "sample" | "offline"

export type Sourced<T> = { data: T; source: Source; error?: string }

export type PdpHealth = {
  status: string
  version?: string
  agent_review?: string
  reviewer_ready?: boolean
  deploy_mode?: string
}

export type Integrity = { ok: boolean; records: number; head?: string; broken_at_line?: number }
