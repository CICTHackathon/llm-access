import type { Metadata } from "next"

import { db } from "@/lib/db"
import type { Role } from "@/lib/roles"
import { requirePage } from "@/lib/session"
import { userSelect } from "@/lib/validations/user"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"
import { UsersManager } from "@/components/users/users-manager"

export const metadata: Metadata = { title: "Users" }

export default async function UsersPage() {
  const user = await requirePage("manageUsers")
  const users = await db.user.findMany({ select: userSelect, orderBy: { createdAt: "asc" } })
  return (
    <Shell>
      <DashboardHeader heading="Users" text="Who can sign in, and what each role may do." />
      <UsersManager
        currentUserId={user.id}
        initialUsers={users.map((u) => ({
          ...u,
          role: u.role as Role,
          lastLoginAt: u.lastLoginAt?.toISOString() ?? null,
          createdAt: u.createdAt.toISOString(),
        }))}
      />
    </Shell>
  )
}
