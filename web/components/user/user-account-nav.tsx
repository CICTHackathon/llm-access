"use client"

import Link from "next/link"
import { signOut } from "next-auth/react"

import type { NavItem } from "@/config/links"
import type { SessionUser } from "@/lib/session"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Icons } from "@/components/icons"
import { UserAvatar } from "@/components/user/user-avatar"

export function UserAccountNav({ user, links }: { user: SessionUser; links: NavItem[] }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account menu">
        <UserAvatar user={{ name: user.name }} className="h-8 w-8" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <div className="flex flex-col space-y-1 p-2 leading-none">
          <p className="font-medium">{user.name}</p>
          <p className="w-[220px] truncate text-sm text-muted-foreground">{user.email}</p>
        </div>
        <DropdownMenuSeparator />
        {links.map((item) => {
          const Icon = Icons[item.icon]
          return (
            <DropdownMenuItem key={item.href} className="cursor-pointer md:hidden" asChild>
              <Link href={item.href}>
                <Icon className="mr-2 h-4 w-4" />
                <span>{item.title}</span>
              </Link>
            </DropdownMenuItem>
          )
        })}
        <DropdownMenuSeparator className="md:hidden" />
        <DropdownMenuItem
          className="cursor-pointer"
          onSelect={(event) => {
            event.preventDefault()
            signOut({ callbackUrl: `${window.location.origin}/signin` })
          }}
        >
          <Icons.signout className="mr-2 h-4 w-4" />
          <span>Sign out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
