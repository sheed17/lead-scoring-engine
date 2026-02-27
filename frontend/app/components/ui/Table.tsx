import React from "react";

export function Table({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`overflow-x-auto ${className}`}><table className="min-w-full text-sm">{children}</table></div>;
}

export function THead({ children }: { children: React.ReactNode }) {
  return <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wider text-[var(--text-muted)]">{children}</thead>;
}

export function TH({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <th className={`px-4 py-3 font-medium ${className}`}>{children}</th>;
}

export function TR({ children }: { children: React.ReactNode }) {
  return <tr className="border-t border-[var(--border-default)] hover:bg-slate-50/60">{children}</tr>;
}

export function TD({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-3 text-[var(--text-secondary)] ${className}`}>{children}</td>;
}
