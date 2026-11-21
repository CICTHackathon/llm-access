import { siteConfig } from "@/config/site"

export default function Footer() {
  return (
    <footer className="mt-auto border-t">
      <div className="container flex flex-col items-center justify-between gap-2 py-5 text-sm text-muted-foreground sm:flex-row">
        <span>
          {siteConfig.name}: policy decisions for{" "}
          <a href={siteConfig.links.hardware} target="_blank" rel="noreferrer" className="hover:underline">
            Smart Gateway
          </a>{" "}
          edge nodes
        </span>
        <span>
          UI based on{" "}
          <a href={siteConfig.links.template} target="_blank" rel="noreferrer" className="hover:underline">
            Iotawise
          </a>{" "}
          (MIT)
        </span>
      </div>
    </footer>
  )
}
