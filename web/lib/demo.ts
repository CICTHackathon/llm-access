/** Demo accounts created by prisma/seed.ts. All share DEMO_PASSWORD. */
export const DEMO_PASSWORD = "Demo1234!"

export const DEMO_ACCOUNTS = [
  { email: "admin@smartgate.demo", name: "Bao Le", role: "ADMIN" },
  { email: "operator@smartgate.demo", name: "Alice Tran", role: "OPERATOR" },
  { email: "auditor@smartgate.demo", name: "Dung Vo", role: "AUDITOR" },
] as const
