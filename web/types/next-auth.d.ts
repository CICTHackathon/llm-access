import type { Role } from "@/lib/roles"

declare module "next-auth" {
  interface Session {
    user: {
      id: string
      name: string
      email: string
      role: Role
    }
  }
  interface User {
    role?: string
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: string
    role?: Role
  }
}
