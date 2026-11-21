"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import type { NavItem } from "@/config/links"
import { cn } from "@/lib/utils"
import { Icons } from "@/components/icons"

export function DashboardNav({ items }: { items: NavItem[] }) {
  const path = usePathname()
  return (
    <nav className="grid items-start gap-1">
      {items.map((item) => {
        const Icon = Icons[item.icon]
        const active = item.href === "/dashboard" ? path === item.href : path.startsWith(item.href)
        return (
          <Link key={item.href} href={item.href}>
            <span
              className={cn(
                "group flex items-center rounded-md px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground",
                active ? "bg-accent" : "transparent"
              )}
            >
              <Icon className="mr-2 h-4 w-4" />
              <span>{item.title}</span>
            </span>
          </Link>
        )
      })}
    </nav>
  )
}
