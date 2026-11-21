/** Server-side configuration, read once. Everything has a working local default. */
export const env = {
  /** Base URL of the llm-access FastAPI (e.g. http://localhost:8080). Empty: sample data. */
  pdpUrl: (process.env.LLM_ACCESS_API_URL ?? "").replace(/\/+$/, ""),
  /** Optional bearer token sent to the PDP, for deployments that put it behind a proxy. */
  pdpToken: process.env.LLM_ACCESS_API_TOKEN ?? "",
  /** "live" talks to the ESP32 nodes; anything else simulates them. */
  iotMode: (process.env.IOT_MODE ?? "mock") === "live" ? ("live" as const) : ("mock" as const),
  /** Seed demo accounts and data into an empty database. */
  seedDemo: (process.env.SEED_DEMO ?? (process.env.NODE_ENV === "production" ? "false" : "true")) === "true",
  /** Timeouts (ms). The operations crew can take a while: it runs several LLM agents. */
  pdpTimeoutMs: Number(process.env.LLM_ACCESS_TIMEOUT_MS ?? 5000),
  chatTimeoutMs: Number(process.env.LLM_ACCESS_CHAT_TIMEOUT_MS ?? 180000),
  deviceTimeoutMs: Number(process.env.IOT_TIMEOUT_MS ?? 4000),
  /** Show the one-click demo accounts on the sign-in page. */
  showDemoAccounts: (process.env.SHOW_DEMO_ACCOUNTS ?? (process.env.NODE_ENV === "production" ? "false" : "true")) === "true",
}
