export const ROLES = ["ADMIN", "OPERATOR", "AUDITOR"] as const
export type Role = (typeof ROLES)[number]

export const ROLE_LABEL: Record<Role, string> = {
  ADMIN: "Administrator",
  OPERATOR: "Operator",
  AUDITOR: "Auditor",
}

export const ROLE_DESCRIPTION: Record<Role, string> = {
  ADMIN: "Everything, including IoT device management, users and the admin audit log.",
  OPERATOR: "Dashboard, access decisions and the operations assistant.",
  AUDITOR: "Read-only dashboard and access decisions.",
}

/** What each capability requires. Pages, API routes and middleware all check these. */
export const PERMISSIONS = {
  viewDashboard: ["ADMIN", "OPERATOR", "AUDITOR"],
  viewDecisions: ["ADMIN", "OPERATOR", "AUDITOR"],
  useAssistant: ["ADMIN", "OPERATOR"],
  manageIot: ["ADMIN"],
  manageUsers: ["ADMIN"],
  viewAudit: ["ADMIN"],
} as const satisfies Record<string, readonly Role[]>

export type Permission = keyof typeof PERMISSIONS

export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value)
}

export function can(role: unknown, permission: Permission): boolean {
  return isRole(role) && (PERMISSIONS[permission] as readonly Role[]).includes(role)
}
