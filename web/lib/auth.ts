import bcrypt from "bcryptjs"
import type { NextAuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { z } from "zod"

import { db } from "@/lib/db"
import { isRole } from "@/lib/roles"

const credentialsSchema = z.object({
  email: z.string().email().transform((v) => v.trim().toLowerCase()),
  password: z.string().min(1),
})

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt", maxAge: 8 * 60 * 60 },
  pages: { signIn: "/signin" },
  providers: [
    CredentialsProvider({
      name: "Email and password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(raw) {
        const parsed = credentialsSchema.safeParse(raw)
        if (!parsed.success) return null
        const user = await db.user.findUnique({ where: { email: parsed.data.email } })
        if (!user || !user.active) return null
        if (!(await bcrypt.compare(parsed.data.password, user.passwordHash))) return null
        await db.user.update({ where: { id: user.id }, data: { lastLoginAt: new Date() } })
        return { id: user.id, name: user.name, email: user.email, role: user.role }
      },
    }),
  ],
  callbacks: {
    // Re-read the user on every token refresh, so a role change or deactivation takes
    // effect immediately instead of when the JWT expires.
    async jwt({ token, user }) {
      const id = (user?.id as string | undefined) ?? token.id
      if (!id) return token
      const dbUser = await db.user.findUnique({ where: { id } })
      if (!dbUser || !dbUser.active || !isRole(dbUser.role)) {
        return { ...token, id, role: undefined }
      }
      return { ...token, id: dbUser.id, name: dbUser.name, email: dbUser.email, role: dbUser.role }
    },
    async session({ session, token }) {
      if (token?.id && token.role) {
        session.user = {
          id: token.id,
          name: token.name ?? "",
          email: token.email ?? "",
          role: token.role,
        }
      } else {
        // Deactivated or deleted since sign-in: the session carries no user.
        session.user = undefined as unknown as typeof session.user
      }
      return session
    },
  },
}
