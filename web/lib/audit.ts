import { db } from "@/lib/db"
import type { SessionUser } from "@/lib/session"

/** Records an administrative action. Never throws: auditing must not break the action. */
export async function audit(
  user: SessionUser,
  action: string,
  target: string,
  detail: Record<string, unknown> = {},
  ok = true
) {
  try {
    await db.auditEntry.create({
      data: { userId: user.id, actorEmail: user.email, action, target, detail: JSON.stringify(detail), ok },
    })
  } catch (error) {
    console.error("audit write failed", error)
  }
}
