"use client"

import type { ColumnDef } from "@tanstack/react-table"

import type { Decision } from "@/lib/types"
import { formatDateTime } from "@/lib/utils"
import { DataTable } from "@/components/data-table"
import { DecisionDetails, EffectBadge } from "@/components/decisions/decision-details"

const columns: ColumnDef<Decision>[] = [
  { id: "time", header: "Time", accessorKey: "decided_at", cell: ({ row }) => formatDateTime(row.original.decided_at) },
  { id: "door", header: "Door", accessorKey: "door" },
  { id: "card", header: "Card", accessorKey: "uid", cell: ({ row }) => <code className="text-xs">{row.original.uid}</code> },
  { id: "subject", header: "Subject", accessorKey: "subject_id", cell: ({ row }) => row.original.subject_id ?? "unknown" },
  { id: "effect", header: "Effect", accessorKey: "effect", cell: ({ row }) => <EffectBadge effect={row.original.effect} /> },
  { id: "reason", header: "Reason", accessorKey: "code", cell: ({ row }) => <code className="text-xs">{row.original.code}</code> },
  {
    id: "agent",
    header: "Agent",
    cell: ({ row }) => (row.original.agent ? `${row.original.agent.effect} (${Math.round(row.original.agent.confidence * 100)}%)` : "not reviewed"),
  },
  { id: "latency", header: "Latency", accessorKey: "latency_ms", cell: ({ row }) => `${row.original.latency_ms} ms` },
  { id: "details", header: "", enableHiding: false, cell: ({ row }) => <DecisionDetails decision={row.original} /> },
]

export function DecisionsTable({ data, title }: { data: Decision[]; title?: string }) {
  return (
    <DataTable columns={columns} data={data}>
      {title}
    </DataTable>
  )
}
