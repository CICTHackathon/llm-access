import type { Metadata } from "next"
import Link from "next/link"

import { siteConfig } from "@/config/site"
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo"
import { env } from "@/lib/env"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { Icons } from "@/components/icons"
import { UserAuthForm } from "@/components/user/user-auth-form"

export const metadata: Metadata = { title: "Sign in" }

export default function SignIn({ searchParams }: { searchParams: { callbackUrl?: string; error?: string } }) {
  // Only same-site paths are accepted as a return address.
  const callbackUrl = searchParams.callbackUrl?.startsWith("/") ? searchParams.callbackUrl : "/dashboard"
  return (
    <main className="container flex min-h-screen flex-col items-center justify-center">
      <Link href="/" className={cn(buttonVariants({ variant: "ghost" }), "absolute left-4 top-4 md:left-8 md:top-8")}>
        <Icons.back className="mr-2 h-4 w-4" />
        Back
      </Link>
      <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[380px]">
        <div className="flex flex-col space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Sign in to {siteConfig.name}</h1>
          <p className="text-sm text-muted-foreground">Accounts are created by an administrator.</p>
        </div>
        <UserAuthForm
          callbackUrl={callbackUrl}
          demo={env.showDemoAccounts ? { password: DEMO_PASSWORD, accounts: [...DEMO_ACCOUNTS] } : null}
        />
      </div>
    </main>
  )
}
