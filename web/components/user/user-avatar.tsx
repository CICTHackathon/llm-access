import type { AvatarProps } from "@radix-ui/react-avatar"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"

/** Initials of the user's name, e.g. "Bao Le" -> "BL". */
export function UserAvatar({ user, ...props }: AvatarProps & { user: { name: string } }) {
  const initials = user.name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("")
  return (
    <Avatar {...props}>
      <AvatarFallback className="text-xs font-semibold">
        <span className="sr-only">{user.name}</span>
        <span aria-hidden>{initials || "?"}</span>
      </AvatarFallback>
    </Avatar>
  )
}
