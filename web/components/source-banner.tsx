import type { Source } from "@/lib/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Icons } from "@/components/icons"

/** Says when data is not live, and why. Renders nothing for live data. */
export function SourceBanner({ source, error, what = "Decisions" }: { source: Source; error?: string; what?: string }) {
  if (source === "live") return null
  return (
    <Alert>
      <Icons.warning className="h-4 w-4" />
      <AlertTitle>{source === "sample" ? "Sample data" : "PDP unreachable"}</AlertTitle>
      <AlertDescription>
        {source === "sample"
          ? `${what} come from the seeded demo database. Set LLM_ACCESS_API_URL to connect the live PDP.`
          : `${what} come from the seeded demo database because the PDP did not answer${error ? `: ${error}` : "."}`}
      </AlertDescription>
    </Alert>
  )
}
