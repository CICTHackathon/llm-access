"use client"

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

import type { CodeCount } from "@/lib/stats"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function DenyCodesChart({ data }: { data: CodeCount[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Why requests were denied</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 items-center gap-2 sm:grid-cols-2">
        {data.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted-foreground sm:col-span-2">No denials in this period.</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={data} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={45} outerRadius={85} stroke="none">
                  {data.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ color: "#000" }} />
              </PieChart>
            </ResponsiveContainer>
            <ul className="space-y-1.5 text-sm">
              {data.map((entry) => (
                <li key={entry.name} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: entry.color }} />
                    <code>{entry.name}</code>
                  </span>
                  <span className="text-muted-foreground">{entry.count}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  )
}
