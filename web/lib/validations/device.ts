import { z } from "zod"

const optionalText = z
  .string()
  .trim()
  .max(200)
  .optional()
  .nullable()
  .transform((v) => (v ? v : null))

export const deviceSchema = z.object({
  id: z.string().trim().regex(/^[a-z0-9][a-z0-9-]{0,31}$/, "Lower-case letters, digits and dashes, e.g. gw-3"),
  kind: z.enum(["gateway", "camera"]),
  name: z.string().trim().min(1).max(80),
  door: optionalText,
  zone: optionalText,
  baseUrl: z.string().trim().url().refine((u) => /^https?:\/\//.test(u), "http(s) URL of the node, e.g. http://192.168.1.53"),
  streamUrl: z
    .string()
    .trim()
    .url()
    .optional()
    .nullable()
    .or(z.literal("").transform(() => null)),
  tokenEnv: z
    .string()
    .trim()
    .regex(/^[A-Z][A-Z0-9_]{0,63}$/, "Name of an environment variable, e.g. GW3_API_TOKEN")
    .optional()
    .nullable()
    .or(z.literal("").transform(() => null)),
  notes: z.string().trim().max(500).optional().nullable(),
})

export const deviceUpdateSchema = deviceSchema.omit({ id: true, kind: true }).partial()

export type DeviceInput = z.infer<typeof deviceSchema>
