import { getServerSession } from "next-auth/next"
import { redirect } from "next/navigation"
import { NextResponse } from "next/server"

import { authOptions } from "@/lib/auth"
import { can, type Permission } from "@/lib/roles"

export type SessionUser = NonNullable<Awaited<ReturnType<typeof getCurrentUser>>>

export async function getCurrentUser() {
  const session = await getServerSession(authOptions)
  return session?.user?.id ? session.user : null
}

/** For server components: sign-in page when signed out, forbidden page when not allowed. */
export async function requirePage(permission: Permission = "viewDashboard"): Promise<SessionUser> {
  const user = await getCurrentUser()
  if (!user) redirect("/signin")
  if (!can(user.role, permission)) redirect("/dashboard/forbidden")
  return user
}

/** For route handlers: the user, or a 401/403 response to return as-is. */
export async function requireApi(
  permission: Permission
): Promise<{ user: SessionUser; error?: never } | { user?: never; error: NextResponse }> {
  const user = await getCurrentUser()
  if (!user) return { error: NextResponse.json({ error: "Sign in required" }, { status: 401 }) }
  if (!can(user.role, permission)) {
    return { error: NextResponse.json({ error: "Your role does not allow this" }, { status: 403 }) }
  }
  return { user }
}
