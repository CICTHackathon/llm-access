import { NextResponse } from "next/server"

import { db } from "@/lib/db"
import { requireApi } from "@/lib/session"

export const dynamic = "force-dynamic"

export async function GET() {
  const { user, error } = await requireApi("useAssistant")
  if (error) return error
  const threads = await db.chatThread.findMany({
    where: { userId: user.id },
    orderBy: { updatedAt: "desc" },
    select: { id: true, title: true, updatedAt: true },
  })
  return NextResponse.json(threads)
}
