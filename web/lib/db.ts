import { PrismaClient } from "@prisma/client"

declare global {
  // eslint-disable-next-line no-var
  var cachedPrisma: PrismaClient | undefined
}

// One client per process; in development, survive hot reloads.
export const db = global.cachedPrisma ?? new PrismaClient()
if (process.env.NODE_ENV !== "production") global.cachedPrisma = db
