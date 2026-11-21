import type { Metadata } from "next"

import { requirePage } from "@/lib/session"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"
import { AppearanceForm } from "@/components/settings/appearance-form"
import { ProfileForm } from "@/components/settings/profile-form"

export const metadata: Metadata = { title: "Settings" }

export default async function SettingsPage() {
  const user = await requirePage("viewDashboard")
  return (
    <Shell>
      <DashboardHeader heading="Settings" text="Your profile, password and appearance." />
      <ProfileForm name={user.name} email={user.email} />
      <AppearanceForm />
    </Shell>
  )
}
