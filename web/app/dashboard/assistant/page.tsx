import type { Metadata } from "next"

import { db } from "@/lib/db"
import { env } from "@/lib/env"
import { getHealth } from "@/lib/pdp"
import { requirePage } from "@/lib/session"
import { Chat } from "@/components/assistant/chat"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"
import { SourceBanner } from "@/components/source-banner"

export const metadata: Metadata = { title: "Assistant" }

export default async function AssistantPage() {
  const user = await requirePage("useAssistant")
  const [threads, health] = await Promise.all([
    db.chatThread.findMany({ where: { userId: user.id }, orderBy: { updatedAt: "desc" }, select: { id: true, title: true, updatedAt: true } }),
    env.pdpUrl ? getHealth() : Promise.resolve(null),
  ])
  const live = health?.source === "live"
  return (
    <Shell>
      <DashboardHeader
        heading="Operations assistant"
        text="Chat with the operations crew: orchestrator, configurator, executor and compliance auditor."
      />
      {!live && <SourceBanner source={health ? "offline" : "sample"} error={health?.error} what="Answers" />}
      <Chat initialThreads={threads.map((t) => ({ ...t, updatedAt: t.updatedAt.toISOString() }))} pdpMode={live ? "live" : "offline"} />
    </Shell>
  )
}
