import { NextResponse } from "next/server"

import { db } from "@/lib/db"
import { requireApi } from "@/lib/session"

export const dynamic = "force-dynamic"

type Params = { params: { threadId: string } }

export async function GET(_req: Request, { params }: Params) {
  const { user, error } = await requireApi("useAssistant")
  if (error) return error
  const thread = await db.chatThread.findFirst({
    where: { id: params.threadId, userId: user.id },
    include: { messages: { orderBy: { createdAt: "asc" } } },
  })
  if (!thread) return NextResponse.json({ error: "No such conversation" }, { status: 404 })
  return NextResponse.json(thread)
}

export async function DELETE(_req: Request, { params }: Params) {
  const { user, error } = await requireApi("useAssistant")
  if (error) return error
  const { count } = await db.chatThread.deleteMany({ where: { id: params.threadId, userId: user.id } })
  if (!count) return NextResponse.json({ error: "No such conversation" }, { status: 404 })
  return new NextResponse(null, { status: 204 })
}
