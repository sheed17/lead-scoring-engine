import React from "react";

export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <section className={`app-card ${className}`}>{children}</section>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between border-b border-[var(--border-default)] px-4 py-3">
      <div>
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-[var(--text-muted)]">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`px-4 py-3 ${className}`}>{children}</div>;
}
