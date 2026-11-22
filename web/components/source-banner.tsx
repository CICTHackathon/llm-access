import type { Source } from "@/lib/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Icons } from "@/components/icons"

/** Says when data is not live, and why. Renders nothing for live data. */
export function SourceBanner({ source, error, what = "Decisions" }: { source: Source; error?: string; what?: string }) {
  if (source === "live") return null
  const title = { sample: "Sample data", offline: "PDP unreachable", empty: "No decisions yet" }[source]
  const text = {
    sample: `${what} come from the seeded demo database. Set LLM_ACCESS_API_URL to connect the live PDP.`,
    offline: `${what} come from the seeded demo database because the PDP did not answer${error ? `: ${error}` : "."}`,
    empty: `${what} come from the seeded demo database because the PDP has not logged any decision yet. Run "llm-access seed-demo" or set LLM_ACCESS_SEED_DEMO=true on the PDP to fill its log.`,
  }[source]
  return (
    <Alert>
      <Icons.warning className="h-4 w-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{text}</AlertDescription>
    </Alert>
  )
}
