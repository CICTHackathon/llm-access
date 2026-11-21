/**
 * Seeds an empty database.
 *
 * - SEED_DEMO=true (default outside production): demo accounts (password "Demo1234!"),
 *   the edge nodes of config/inventory.yaml, two weeks of sample decisions, chats and audit entries.
 * - ADMIN_EMAIL / ADMIN_PASSWORD: creates that administrator instead, for a real deployment.
 *
 * Safe to run repeatedly: it does nothing once users exist.
 */
import bcrypt from "bcryptjs"
import { PrismaClient } from "@prisma/client"

import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "../lib/demo"

const db = new PrismaClient()
const isProduction = process.env.NODE_ENV === "production"
const seedDemo = (process.env.SEED_DEMO ?? (isProduction ? "false" : "true")) === "true"

// Mirrors config/inventory.yaml. Tokens stay in the environment variables named here.
const DEVICES = [
  {
    id: "gw-1",
    kind: "gateway",
    name: "Engineering lab gateway",
    door: "door-1",
    zone: "engineering",
    baseUrl: "http://192.168.1.50",
    tokenEnv: "GW1_API_TOKEN",
    notes: "ESP32 DevKit V1 + RC522, 4x4 keypad, LCD 2004A, SG90 latch, buzzer.",
  },
  {
    id: "cam-1",
    kind: "camera",
    name: "Engineering lab recorder",
    door: "door-1",
    zone: "engineering",
    baseUrl: "http://192.168.1.51",
    streamUrl: "http://192.168.1.51:81/stream",
    notes: "ESP32-CAM (OV2640) + microSD. Recordings over WebDAV at /dav.",
  },
  {
    id: "gw-2",
    kind: "gateway",
    name: "Server room gateway",
    door: "door-2",
    zone: "server_room",
    baseUrl: "http://192.168.1.52",
    tokenEnv: "GW2_API_TOKEN",
    notes: "ESP32 DevKit V1 + RC522, 4x4 keypad, LCD 2004A, SG90 latch, buzzer.",
  },
]

// ------------------------------------------------------------------ decisions

// Deterministic, so every fresh demo database looks the same.
function prng(seed: number) {
  return () => {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const rand = prng(20261121)
const pick = <T,>(items: readonly T[]) => items[Math.floor(rand() * items.length)]
const hex = (n: number) => Array.from({ length: n }, () => Math.floor(rand() * 16).toString(16)).join("")

type Outcome = {
  uid: string
  subject: string | null
  door: "door-1" | "door-2"
  failAt?: "identify" | "authenticate" | "authorize" | "risk" | "agent_review"
  code: string
  rule?: string
  risk?: { code: string; severity: "info" | "warn" | "critical"; detail: string }[]
  agent?: { effect: "permit" | "deny"; confidence: number; code: string; reasons: string[]; cited_policies: string[] }
}

// Scenarios from config/identities.yaml and config/policies.yaml, weighted by how often they happen.
const SCENARIOS: [weight: number, make: (hour: number) => Outcome][] = [
  [30, (h) => (h >= 7 && h < 20
    ? { uid: "0xa1b2c3d4", subject: "alice", door: "door-1", code: "permit", rule: "R-STAFF-DEPT" }
    : { uid: "0xa1b2c3d4", subject: "alice", door: "door-1", failAt: "authorize", code: "outside_schedule" })],
  [14, () => ({ uid: "0xb2c3d4e5", subject: "bao", door: pick(["door-1", "door-2"] as const), code: "permit", rule: "R-ADMIN-ANYTIME" })],
  [10, (h) => (h >= 8 && h < 18
    ? { uid: "0xc3d4e5f6", subject: "chi", door: "door-1", code: "permit", rule: "R-CONTRACTOR-HOURS" }
    : { uid: "0xc3d4e5f6", subject: "chi", door: "door-1", failAt: "authorize", code: "outside_schedule" })],
  [6, () => ({ uid: "0xa1b2c3d4", subject: "alice", door: "door-2", failAt: "authorize", code: "insufficient_clearance" })],
  [5, () => ({ uid: "0xd4e5f607", subject: "dung", door: "door-2", failAt: "authorize", code: "explicit_deny", rule: "D-INTERN-SERVER-ROOM" })],
  [3, () => ({ uid: "0xe5f60718", subject: "em", door: "door-1", failAt: "identify", code: "subject_suspended" })],
  [3, () => ({ uid: "0xf6071829", subject: "alice", door: "door-1", failAt: "identify", code: "card_revoked" })],
  [4, () => ({ uid: "0xa1b2c3d4", subject: "alice", door: "door-1", failAt: "authenticate", code: "bad_pin" })],
  [2, () => ({ uid: "0xdeadbeef", subject: null, door: pick(["door-1", "door-2"] as const), failAt: "identify", code: "unknown_card" })],
  [3, () => ({
    uid: "0xc3d4e5f6", subject: "chi", door: "door-1", failAt: "agent_review", code: "tailgate_risk", rule: "R-CONTRACTOR-HOURS",
    risk: [{ code: "unattested_motion", severity: "warn", detail: "Two motion events at cam-1 within 20 s after one grant." }],
    agent: { effect: "deny", confidence: 0.86, code: "tailgate_risk", reasons: ["Recent motion without a matching credential suggests tailgating."], cited_policies: ["G-TAILGATE"] },
  })],
  [2, () => ({
    uid: "0xa1b2c3d4", subject: "alice", door: "door-1", failAt: "risk", code: "denial_velocity",
    risk: [{ code: "denial_velocity", severity: "critical", detail: "5 denials on door-1 within 2 minutes." }],
  })],
]
const TOTAL = SCENARIOS.reduce((n, [w]) => n + w, 0)

function scenario(hour: number): Outcome {
  let r = rand() * TOTAL
  for (const [w, make] of SCENARIOS) {
    if ((r -= w) <= 0) return make(hour)
  }
  return SCENARIOS[0][1](hour)
}

const STAGE_NAMES = ["validate", "identify", "authenticate", "authorize", "risk", "agent_review"] as const

function stagesFor(o: Outcome) {
  const stages = []
  for (const name of STAGE_NAMES) {
    const failed = o.failAt === name
    const passCode: Record<string, string> = {
      validate: "trusted_gateway",
      identify: "active_subject",
      authenticate: "pin_ok",
      authorize: "permit",
      risk: o.risk?.length ? "forwarded" : "no_signals",
      agent_review: "consistent",
    }
    stages.push({ name, passed: !failed, code: failed ? o.code : passCode[name], detail: failed ? `Stopped: ${o.code}` : "" })
    if (failed) break
  }
  return stages
}

function decisionsFor(days: number) {
  const rows = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  for (let back = days - 1; back >= 0; back--) {
    const day = new Date(today.getTime() - back * 86400_000)
    const weekend = day.getDay() === 0 || day.getDay() === 6
    const count = weekend ? 3 + Math.floor(rand() * 4) : 12 + Math.floor(rand() * 10)
    for (let i = 0; i < count; i++) {
      const hour = rand() < 0.88 ? 7 + Math.floor(rand() * 12) : pick([5, 6, 20, 21, 22])
      const at = new Date(day.getTime() + hour * 3600_000 + Math.floor(rand() * 3600_000))
      if (at > new Date()) continue
      const o = scenario(hour)
      const permit = !o.failAt
      const reviewed = permit && rand() < 0.6
      const agent = o.agent ?? (reviewed
        ? { effect: "permit" as const, confidence: Number((0.8 + rand() * 0.18).toFixed(2)), code: "consistent", reasons: ["No guidance statement applies; door evidence is consistent."], cited_policies: [] }
        : null)
      rows.push({
        id: `dec-${hex(12)}`,
        txn: hex(16),
        door: o.door,
        uid: o.uid,
        subjectId: o.subject,
        effect: permit ? "permit" : "deny",
        code: o.code,
        stages: JSON.stringify(stagesFor(o).filter((s) => s.name !== "agent_review" || agent)),
        matched: JSON.stringify(o.rule ? [o.rule] : []),
        risk: JSON.stringify(o.risk ?? []),
        agent: agent ? JSON.stringify(agent) : null,
        latencyMs: agent ? 1800 + Math.floor(rand() * 4200) : 40 + Math.floor(rand() * 160),
        decidedAt: at,
      })
    }
  }
  return rows
}

// ------------------------------------------------------------------ main

async function main() {
  if ((await db.user.count()) > 0) {
    console.log("Database already has users; nothing to seed.")
    return
  }

  if (!seedDemo) {
    const email = process.env.ADMIN_EMAIL?.trim().toLowerCase()
    const password = process.env.ADMIN_PASSWORD
    if (!email || !password) {
      console.log("SEED_DEMO is off and ADMIN_EMAIL/ADMIN_PASSWORD are not set: no users created.")
      return
    }
    await db.user.create({
      data: { email, name: "Administrator", role: "ADMIN", passwordHash: await bcrypt.hash(password, 12) },
    })
    for (const d of DEVICES) await db.device.upsert({ where: { id: d.id }, update: {}, create: d })
    console.log(`Created administrator ${email} and ${DEVICES.length} devices.`)
    return
  }

  const passwordHash = await bcrypt.hash(DEMO_PASSWORD, 10)
  const users: Record<string, { id: string; email: string }> = {}
  for (const a of DEMO_ACCOUNTS) {
    users[a.role] = await db.user.create({ data: { ...a, passwordHash } })
  }
  for (const d of DEVICES) await db.device.upsert({ where: { id: d.id }, update: {}, create: d })

  const decisions = decisionsFor(14)
  await db.decisionSample.createMany({ data: decisions })

  const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000)
  const threads = [
    {
      user: users.OPERATOR,
      title: "Sync the offline cache of door-1",
      at: ago(180),
      turns: [
        ["user", "Sync the offline cache of door-1 and raise its PDP timeout to 25 s"],
        [
          "assistant",
          "**Outcome:** applied (dry run)\n\nThe configurator derived the offline cache of door-1 from the live policy and the verifier issued two plans; the executor applied both and read the device back.\n\n**Plans applied**\n- plan-7f3a: offline ACL for gw-1 (2 entries, TTL ends with each rule's schedule window)\n- plan-91c2: gw-1 pdpTimeoutMs 20000 -> 25000\n\n**Findings**\n- Baseline compliance: 0 critical, 1 warning (cam-1 recorder API is unauthenticated; keep it on the isolated network)",
        ],
      ],
    },
    {
      user: users.ADMIN,
      title: "Why was the intern denied at the server room?",
      at: ago(60 * 26),
      turns: [
        ["user", "Why was dung denied at door-2 this morning?"],
        [
          "assistant",
          "**Outcome:** explained\n\nThe request stopped at **authorize**: rule `D-INTERN-SERVER-ROOM` denies interns access to the server room, and deny-overrides makes it final. The card and PIN were valid.\n\n**Follow-up**\n- If Dung needs supervised access, add a time-boxed exception rule and run the policy regression scenarios before deploying it.",
        ],
      ],
    },
  ] as const
  for (const t of threads) {
    await db.chatThread.create({
      data: {
        userId: t.user.id,
        title: t.title,
        createdAt: t.at,
        updatedAt: t.at,
        messages: {
          create: t.turns.map(([role, content], i) => ({ role, content, mode: "live", createdAt: new Date(t.at.getTime() + i * 40_000) })),
        },
      },
    })
  }

  const admin = users.ADMIN
  const auditRows = [
    { action: "device.unlock", target: "gw-1", detail: { reason: "Delivery at the engineering lab" }, at: ago(60 * 30) },
    { action: "device.config", target: "gw-1", detail: { key: "pdpTimeoutMs", value: 25000 }, at: ago(60 * 20) },
    { action: "user.create", target: "auditor@smartgate.demo", detail: { role: "AUDITOR" }, at: ago(60 * 24 * 6) },
    { action: "recording.delete", target: "cam-1:/events/old", detail: { reason: "Retention" }, at: ago(60 * 24 * 2) },
  ]
  for (const r of auditRows) {
    await db.auditEntry.create({
      data: { userId: admin.id, actorEmail: admin.email, action: r.action, target: r.target, detail: JSON.stringify(r.detail), createdAt: r.at },
    })
  }

  console.log(
    `Seeded demo data: ${DEMO_ACCOUNTS.length} accounts (password "${DEMO_PASSWORD}"), ${DEVICES.length} devices, ` +
      `${decisions.length} sample decisions, ${threads.length} chats, ${auditRows.length} audit entries.`
  )
}

main()
  .catch((error) => {
    console.error(error)
    process.exit(1)
  })
  .finally(() => db.$disconnect())
