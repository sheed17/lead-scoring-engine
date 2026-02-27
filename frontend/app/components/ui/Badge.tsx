import React from "react";

type Props = {
  children: React.ReactNode;
  tone?: "default" | "success" | "danger" | "muted";
};

const tones: Record<NonNullable<Props["tone"]>, string> = {
  default: "bg-[var(--accent-soft)] text-[var(--accent)]",
  success: "bg-emerald-50 text-emerald-700",
  danger: "bg-rose-50 text-rose-700",
  muted: "bg-slate-100 text-slate-700",
};

export default function Badge({ children, tone = "muted" }: Props) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
