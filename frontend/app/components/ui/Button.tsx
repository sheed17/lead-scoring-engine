import React from "react";

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
};

const variants: Record<NonNullable<Props["variant"]>, string> = {
  primary: "bg-[var(--accent)] text-[var(--accent-ink)] hover:brightness-95 border border-transparent",
  secondary: "bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-default)] hover:bg-slate-50",
  ghost: "bg-transparent text-[var(--text-secondary)] border border-transparent hover:bg-slate-100",
};

export default function Button({ variant = "secondary", className = "", ...props }: Props) {
  return (
    <button
      {...props}
      className={`h-9 rounded-[var(--radius-md)] px-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${variants[variant]} ${className}`}
    />
  );
}
