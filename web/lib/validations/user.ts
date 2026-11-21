import { z } from "zod"

import { ROLES } from "@/lib/roles"

export const password = z
  .string()
  .min(8, "At least 8 characters")
  .max(128)
  .regex(/[A-Za-z]/, "Include a letter")
  .regex(/[0-9]/, "Include a digit")

export const userCreateSchema = z.object({
  name: z.string().trim().min(1).max(80),
  email: z.string().trim().toLowerCase().email(),
  role: z.enum(ROLES),
  password,
})

export const userUpdateSchema = z.object({
  name: z.string().trim().min(1).max(80).optional(),
  role: z.enum(ROLES).optional(),
  active: z.boolean().optional(),
  password: password.optional(),
})

export const profileSchema = z
  .object({
    name: z.string().trim().min(1).max(80).optional(),
    currentPassword: z.string().optional(),
    newPassword: password.optional(),
  })
  .refine((v) => !v.newPassword || v.currentPassword, { message: "Enter your current password", path: ["currentPassword"] })

export function issues(error: z.ZodError) {
  return error.issues.map((i) => (i.path.length ? `${i.path.join(".")}: ${i.message}` : i.message)).join("; ")
}

/** Columns returned by the users API: never the password hash. */
export const userSelect = {
  id: true,
  name: true,
  email: true,
  role: true,
  active: true,
  lastLoginAt: true,
  createdAt: true,
} as const
