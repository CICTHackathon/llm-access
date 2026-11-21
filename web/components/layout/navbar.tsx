import Link from "next/link"

import type { NavItem } from "@/config/links"
import { siteConfig } from "@/config/site"
import { ROLE_LABEL } from "@/lib/roles"
import type { SessionUser } from "@/lib/session"
import { Badge } from "@/components/ui/badge"
import { ModeToggle } from "@/components/mode-toggle"
import { UserAccountNav } from "@/components/user/user-account-nav"

export default function Navbar({ user, links }: { user: SessionUser; links: NavItem[] }) {
  return (
    <header className="sticky top-0 z-40 select-none border-b bg-background/95 backdrop-blur">
      <nav className="container flex items-center justify-between py-3">
        <Link href="/dashboard" className="text-xl font-bold">
          {siteConfig.name}
        </Link>
        <div className="flex items-center gap-3">
          <Badge variant={user.role === "ADMIN" ? "default" : "secondary"} className="hidden sm:inline-flex">
            {ROLE_LABEL[user.role]}
          </Badge>
          <ModeToggle />
          <UserAccountNav user={user} links={links} />
        </div>
      </nav>
    </header>
  )
}
