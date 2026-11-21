import { NextResponse } from "next/server"
import { z } from "zod"

import { db } from "@/lib/db"
import { askAssistant, type ChatTurn } from "@/lib/pdp"
import { requireApi } from "@/lib/session"

export const dynamic = "force-dynamic"
export const maxDuration = 300

const bodySchema = z.object({
  threadId: z.string().optional(),
  message: z.string().trim().min(1).max(4000),
})

/** Adds a user message to a thread (new or existing) and returns the assistant's answer. */
export async function POST(req: Request) {
  const { user, error } = await requireApi("useAssistant")
  if (error) return error
  const parsed = bodySchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: "A non-empty message is required" }, { status: 400 })
  const { threadId, message } = parsed.data

  const thread = threadId
    ? await db.chatThread.findFirst({ where: { id: threadId, userId: user.id } })
    : await db.chatThread.create({ data: { userId: user.id, title: message.slice(0, 80) } })
  if (!thread) return NextResponse.json({ error: "No such conversation" }, { status: 404 })

  await db.chatMessage.create({ data: { threadId: thread.id, role: "user", content: message } })
  const history = await db.chatMessage.findMany({
    where: { threadId: thread.id },
    orderBy: { createdAt: "asc" },
    take: 40,
  })
  const turns: ChatTurn[] = history.map((m) => ({ role: m.role === "user" ? "user" : "assistant", content: m.content }))
  const answer = await askAssistant(turns)
  const saved = await db.chatMessage.create({
    data: { threadId: thread.id, role: "assistant", content: answer.content, mode: answer.mode },
  })
  await db.chatThread.update({ where: { id: thread.id }, data: { updatedAt: new Date() } })

  return NextResponse.json({ threadId: thread.id, title: thread.title, message: saved })
}
