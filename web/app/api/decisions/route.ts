import { NextResponse } from "next/server"

import { listDecisions } from "@/lib/pdp"
import { requireApi } from "@/lib/session"

export const dynamic = "force-dynamic"

export async function GET(req: Request) {
  const { error } = await requireApi("viewDecisions")
  if (error) return error
  const q = new URL(req.url).searchParams
  const result = await listDecisions({
    limit: Number(q.get("limit") ?? 50),
    door: q.get("door") ?? undefined,
    uid: q.get("uid") ?? undefined,
  })
  return NextResponse.json(result)
}
