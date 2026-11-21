import Link from "next/link"
import { redirect } from "next/navigation"

import { siteConfig } from "@/config/site"
import { getCurrentUser } from "@/lib/session"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { Icons } from "@/components/icons"
import { ModeToggle } from "@/components/mode-toggle"

const FEATURES = [
  { icon: "decisions", title: "Access decisions", text: "Every card-and-PIN request the gateways send, with the stage that decided it." },
  { icon: "chat", title: "Operations assistant", text: "Ask in plain language; the agent crew plans, verifies, deploys and audits." },
  { icon: "devices", title: "IoT management", text: "Gateways and cameras in one place: status, overrides, settings and recordings." },
  { icon: "users", title: "Role-based access", text: "Administrators, operators and auditors each see what their role allows." },
] as const

export default async function Home() {
  if (await getCurrentUser()) redirect("/dashboard")
  return (
    <main className="container flex flex-1 flex-col">
      <header className="flex items-center justify-between py-5">
        <span className="text-2xl font-bold">{siteConfig.name}</span>
        <div className="flex items-center gap-2">
          <ModeToggle />
          <Link href="/signin" className={cn(buttonVariants({ size: "sm" }))}>
            Sign in
          </Link>
        </div>
      </header>
      <section className="mx-auto flex max-w-3xl flex-1 flex-col items-center justify-center gap-6 py-16 text-center">
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Smart gates, one console</h1>
        <p className="text-lg text-muted-foreground">{siteConfig.description}</p>
        <Link href="/signin" className={cn(buttonVariants({ size: "lg" }))}>
          Sign in to the dashboard
        </Link>
        <div className="mt-10 grid w-full gap-4 text-left sm:grid-cols-2">
          {FEATURES.map((f) => {
            const Icon = Icons[f.icon]
            return (
              <div key={f.title} className="rounded-lg border p-5">
                <Icon className="mb-3 h-6 w-6 text-primary" />
                <h2 className="font-semibold">{f.title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{f.text}</p>
              </div>
            )
          })}
        </div>
      </section>
    </main>
  )
}
