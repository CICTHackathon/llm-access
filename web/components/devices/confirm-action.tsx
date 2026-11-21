"use client"

import * as React from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button, type ButtonProps } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

/** A button that asks for confirmation (and optionally a reason) before running `onConfirm`. */
export function ConfirmAction({
  label,
  title,
  description,
  askReason = false,
  variant = "outline",
  disabled,
  onConfirm,
}: {
  label: React.ReactNode
  title: string
  description: string
  askReason?: boolean
  variant?: ButtonProps["variant"]
  disabled?: boolean
  onConfirm: (reason: string) => Promise<void> | void
}) {
  const [reason, setReason] = React.useState("")
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant={variant} disabled={disabled}>
          {label}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {askReason && <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason, kept in the audit log" />}
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={askReason && !reason.trim()} onClick={() => onConfirm(reason.trim())}>
            Confirm
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
