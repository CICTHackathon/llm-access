import type { IconKeys } from "@/components/icons"
import type { Permission } from "@/lib/roles"

export type NavItem = { title: string; href: string; icon: IconKeys; permission: Permission }

/** Dashboard navigation; each entry is shown only to roles holding its permission. */
export const dashboardLinks: NavItem[] = [
  { title: "Overview", href: "/dashboard", icon: "dashboard", permission: "viewDashboard" },
  { title: "Decisions", href: "/dashboard/decisions", icon: "decisions", permission: "viewDecisions" },
  { title: "Assistant", href: "/dashboard/assistant", icon: "chat", permission: "useAssistant" },
  { title: "IoT devices", href: "/dashboard/devices", icon: "devices", permission: "manageIot" },
  { title: "Users", href: "/dashboard/users", icon: "users", permission: "manageUsers" },
  { title: "Audit log", href: "/dashboard/audit", icon: "audit", permission: "viewAudit" },
  { title: "Settings", href: "/dashboard/settings", icon: "settings", permission: "viewDashboard" },
]
