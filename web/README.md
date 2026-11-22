# LLM Access Web Interface

The web interface of the PDP: a dashboard of access decisions, a chat with the operations
assistant, and administrator-only management of the ESP32 edge nodes. It is a Next.js 14
application built on the [Iotawise](https://github.com/redpangilinan/iotawise) template (MIT,
see `LICENSE.iotawise`), with credentials sign-in, roles, Prisma and SQLite.

## Roles

| Capability | Administrator | Operator | Auditor |
|---|:-:|:-:|:-:|
| Overview and access decisions | ✓ | ✓ | ✓ |
| Operations assistant (chat) | ✓ | ✓ | |
| IoT devices: gateway consoles, camera views, recordings | ✓ | | |
| Users and roles | ✓ | | |
| Admin audit log | ✓ | | |

`middleware.ts` sends signed-out visitors to the sign-in page. Every page (`requirePage`)
and every API route (`requireApi`) then checks the role, read from the database on each
request, so promoting, demoting or deactivating a user takes effect immediately without a
new sign-in. Navigation only lists what the role may open. The roles and their
permissions are defined in `lib/roles.ts`.

## How it connects

```
browser ──> Next.js (this app) ──> llm-access PDP      /pdp/decisions, /pdp/integrity, /health,
              │  roles, sessions,                       /v1/chat/completions (operations crew)
              │  audit log
              └──────────────────> ESP32 gateway        /api/status, /events, /acl, /config,
                                    ESP32-CAM recorder  /unlock, /lock, /enrol, /capture, /dav/...
```

The browser never talks to the PDP or the nodes. The server calls them, so device tokens
stay in server environment variables (each device names its variable, e.g.
`GW1_API_TOKEN`), secret settings are masked before they reach the page, and every
change made through the interface is written to the admin audit log.

The IoT pages bring together what the [iot-hardware](https://github.com/CICTHackathon/iot-hardware)
nodes expose:

- **Gateways:** status, operator override (unlock, lock), card enrolment, the audit ring,
  the offline cache (revoke entries, clear), settings, reboot.
- **Cameras:** a live frame every 2 seconds from `/capture`, a link to the MJPEG stream on
  port 81, movement events with person / not-person labelling, the WebDAV recordings share
  (browse day folders, view a JPEG or its JSON sidecar, download, delete) and settings.
- **Device console:** each node's own operator page (`console/index.html`), opened or
  embedded from the device network.

## Running locally

Node 20 or later and pnpm.

```bash
cd web
cp .env.example .env          # set NEXTAUTH_SECRET to a long random string
pnpm install
pnpm dev                      # creates the SQLite database, seeds it, starts http://localhost:3000
```

`pnpm dev` runs `prisma db push` and the seed first; both are safe to repeat. Use
`pnpm db:reset` to start again from a fresh demo database.

### Demo accounts

With `SEED_DEMO=true` (the default outside production) an empty database is seeded with the
accounts below, and the sign-in page offers them as one-click buttons. The password for all
of them is `Demo1234!`.

| Email | Role |
|---|---|
| `admin@smartgate.demo` | Administrator |
| `operator@smartgate.demo` | Operator |
| `auditor@smartgate.demo` | Auditor |

The seed also creates the three edge nodes of `config/inventory.yaml` (gw-1, cam-1, gw-2),
two weeks of sample access decisions that follow `config/identities.yaml` and
`config/policies.yaml`, two assistant conversations and a few audit entries.

### Demo mode and live mode

| Setting | Empty or `mock` (default) | Set or `live` |
|---|---|---|
| `LLM_ACCESS_API_URL` | Decisions come from the seeded samples; the assistant answers offline from local data | Decisions, log integrity and the assistant come from the PDP (`llm-access serve`) |
| `IOT_MODE` | The nodes are simulated from the seeded decisions | The server calls the ESP32 nodes at the addresses on the Devices page |

When the PDP is configured but does not answer, or answers with an empty decision log, pages fall back to the samples and say so. To give a PDP its own data, run `llm-access seed-demo` or start it with `LLM_ACCESS_SEED_DEMO=true`.

To run against the real system:

```bash
llm-access serve --host 0.0.0.0 --port 8080           # in the repository root
# web/.env
LLM_ACCESS_API_URL=http://localhost:8080
IOT_MODE=live
GW1_API_TOKEN=...                                    # the token gw-1 printed at first boot
GW2_API_TOKEN=...
```

### Production

Set `NODE_ENV=production`, a strong `NEXTAUTH_SECRET` and the public `NEXTAUTH_URL`.
Demo seeding and the demo-account buttons are then off; set `ADMIN_EMAIL` and
`ADMIN_PASSWORD` once to create the first administrator on an empty database. For
several instances, switch `prisma/schema.prisma` to PostgreSQL.

```bash
pnpm build && pnpm db:setup && pnpm start
```

## Structure

```
web/
├── app/                 # Next.js routes
│   ├── (auth)/signin/   # Sign-in with demo accounts
│   ├── dashboard/       # Overview, decisions, assistant, devices, users, audit, settings
│   └── api/             # Route handlers: chat, threads, decisions, devices/*, users, me
├── components/          # UI (shadcn/ui), charts, chat, device consoles, user management
├── lib/
│   ├── auth.ts          # NextAuth credentials provider, role in the session
│   ├── roles.ts         # Roles and permissions
│   ├── session.ts       # requirePage / requireApi guards
│   ├── pdp.ts           # Client for the llm-access PDP, with sample and offline fallbacks
│   └── iot/             # Gateway and camera clients: live (HTTP, WebDAV) and simulated
├── prisma/              # Schema and seed
└── middleware.ts        # Sign-in gate
```
