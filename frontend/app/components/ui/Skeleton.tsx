import React from "react";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-[var(--radius-md)] bg-slate-200 ${className}`} />;
}
