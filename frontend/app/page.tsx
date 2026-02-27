"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

const navItems = ["Product", "Use cases", "Solutions", "Resources", "Company", "Pricing"];

const metrics = [
  { label: "Signals per brief", value: "40+" },
  { label: "Prospects ranked", value: "Top 20" },
  { label: "Fast shortlist mode", value: "~15-30s" },
  { label: "Verified service-page mode", value: "10-25 min" },
];

const workflows = [
  {
    title: "Run territory scan first",
    body: "Start with market-wide ranking to identify where leverage is concentrated before narrowing to exact criteria.",
    step: "01",
  },
  {
    title: "Use Ask Neyma for intent filters",
    body: "Query in plain English and choose Fast mode for speed or Verified mode for stricter service-page accuracy.",
    step: "02",
  },
  {
    title: "Open full brief on demand",
    body: "Build full diagnostics only for shortlisted prospects, then move winners into lists and outcomes.",
    step: "03",
  },
];

const comparison = [
  {
    label: "Data model",
    generic: "Contact records + enrichment snippets",
    neyma: "Deterministic revenue intelligence with market context",
  },
  {
    label: "Workflow",
    generic: "Search tool + manual ops across tabs",
    neyma: "Intent -> scan -> rank -> brief -> outcome in one workspace",
  },
  {
    label: "Prioritization",
    generic: "Sort by firmographics or generic score",
    neyma: "Rank by structural revenue leverage and conversion readiness",
  },
  {
    label: "Execution",
    generic: "Export and continue elsewhere",
    neyma: "Lists, outcomes, exports, and monitoring in-platform",
  },
];

const faq = [
  {
    q: "Does Neyma replace my CRM?",
    a: "No. Neyma is your intelligence and prioritization layer before and alongside CRM execution.",
  },
  {
    q: "Do I need full briefs for every prospect?",
    a: "No. Run territory + Ask first, then generate deep briefs only for selected prospects.",
  },
  {
    q: "How accurate is Ask Neyma for service-page requests?",
    a: "Ask Fast returns likely matches quickly, while Ask Verified runs deeper validation and takes longer for higher precision.",
  },
  {
    q: "Can agencies run multiple markets?",
    a: "Yes. Neyma is built for multi-territory workflows and repeatable prospecting operations.",
  },
];

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
      <header className="sticky top-0 z-40 border-b border-[var(--border-default)]/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[var(--max-content)] items-center justify-between px-4 sm:px-6">
          <Link href="/" className="display-title text-2xl font-black tracking-tight">
            neyma
          </Link>
          <nav className="hidden items-center gap-7 text-sm text-[var(--text-secondary)] lg:flex">
            {navItems.map((item) => (
              <a key={item} href="#" className="transition hover:text-[var(--text-primary)]">
                {item}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            {user ? (
              <Link href="/dashboard" className="inline-flex h-10 items-center rounded-full bg-black px-4 text-sm font-semibold text-white transition hover:opacity-90">
                Open workspace
              </Link>
            ) : (
              <>
                <Link href="/login" className="hidden rounded-full px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] sm:inline-flex">
                  Log in
                </Link>
                <Link href="/register" className="inline-flex h-10 items-center rounded-full bg-black px-4 text-sm font-semibold text-white transition hover:opacity-90">
                  Start free
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        <section className="px-4 pb-8 pt-8 sm:px-6 sm:pt-12">
          <div className="mx-auto max-w-[var(--max-content)] rounded-[34px] border border-[var(--border-default)] bg-[#f3f3f0] p-5 sm:p-10">
            <div className="relative overflow-hidden rounded-[28px] border border-white/60 bg-gradient-to-br from-[#f8f7f2] via-[#f2f5f9] to-[#e8edf3] px-6 py-14 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.45)] sm:px-16 sm:py-20">
              <div className="pointer-events-none absolute inset-0 opacity-80 [background:radial-gradient(circle_at_20%_20%,rgba(13,148,136,0.12),transparent_45%),radial-gradient(circle_at_80%_20%,rgba(59,130,246,0.12),transparent_35%),radial-gradient(circle_at_60%_80%,rgba(236,72,153,0.09),transparent_30%)]" />
              <div className="relative mx-auto max-w-4xl text-center">
                <p className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">Revenue Intelligence Platform</p>
                <h1 className="display-title text-balance text-4xl font-black leading-[1.03] tracking-tight sm:text-6xl md:text-7xl">
                  Turn market noise into
                  <span className="block bg-gradient-to-r from-[#0d9488] to-[#2563eb] bg-clip-text text-transparent">
                    ranked revenue opportunities
                  </span>
                </h1>
                <p className="mx-auto mt-6 max-w-2xl text-base text-[var(--text-secondary)] sm:text-xl">
                  Neyma is built for territory-first prospecting. Scan a market, then use Ask Neyma in fast or verified mode to filter prospects with the right balance of speed and accuracy.
                </p>
                <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                  <Link href={user ? "/territory/new" : "/register"} className="inline-flex h-12 min-w-[210px] items-center justify-center rounded-full bg-black px-7 text-sm font-semibold text-white transition hover:opacity-90">
                    Run territory scan
                  </Link>
                  <Link href={user ? "/ask" : "/login"} className="inline-flex h-12 min-w-[190px] items-center justify-center rounded-full border border-[var(--border-default)] bg-white px-7 text-sm font-semibold text-[var(--text-primary)] transition hover:bg-[#f8fafc]">
                    Ask Neyma
                  </Link>
                </div>
                <p className="mt-3 text-xs font-medium text-[var(--text-muted)]">
                  Start with territory scan for market prioritization. Use Ask Neyma Fast (~15-30s) or Verified mode (10-25 min) for strict service-page validation.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="px-4 pb-6 sm:px-6">
          <div className="mx-auto max-w-[var(--max-content)] rounded-3xl border border-[var(--border-default)] bg-white px-6 py-7">
            <p className="text-center text-xs font-semibold uppercase tracking-[0.22em] text-[var(--text-muted)]">
              Built for agencies running repeatable local growth workflows
            </p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {metrics.map((metric) => (
                <div key={metric.label} className="rounded-2xl border border-[var(--border-default)] bg-[#f8fafc] p-4 text-center">
                  <div className="display-title text-2xl font-black tracking-tight">{metric.value}</div>
                  <div className="mt-1 text-xs uppercase tracking-wide text-[var(--text-muted)]">{metric.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="px-4 py-8 sm:px-6 sm:py-12">
          <div className="mx-auto grid max-w-[var(--max-content)] gap-5 lg:grid-cols-3">
            {workflows.map((item) => (
              <article key={item.step} className="rounded-3xl border border-[var(--border-default)] bg-white p-6">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">Step {item.step}</p>
                <h2 className="display-title mt-3 text-2xl font-bold leading-tight text-[var(--text-primary)]">{item.title}</h2>
                <p className="mt-4 text-sm leading-relaxed text-[var(--text-secondary)]">{item.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="px-4 py-8 sm:px-6 sm:py-12">
          <div className="mx-auto max-w-[var(--max-content)] rounded-[30px] bg-[#0b1220] px-6 py-10 text-white sm:px-10 sm:py-14">
            <div className="grid gap-8 lg:grid-cols-[1.2fr_1fr] lg:items-center">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">Why Neyma</p>
                <h3 className="display-title mt-3 text-3xl font-black tracking-tight sm:text-5xl">Purpose-built for prioritization, not just prospect search.</h3>
                <p className="mt-4 max-w-2xl text-slate-300">
                  Major lead databases are broad. Neyma is intentionally opinionated for local service revenue leverage, so teams know which prospects to contact first.
                </p>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-5 sm:p-6">
                <div className="space-y-3 text-sm">
                  <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">Territory-first prioritization across local markets</div>
                  <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">Ask Fast for speed, Ask Verified for precision</div>
                  <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">Deep briefs only when you request them</div>
                </div>
                <Link href={user ? "/dashboard" : "/register"} className="mt-5 inline-flex h-11 items-center rounded-full bg-[var(--accent)] px-5 text-sm font-semibold text-white transition hover:brightness-95">
                  {user ? "Open dashboard" : "Create workspace"}
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="px-4 py-8 sm:px-6 sm:py-12">
          <div className="mx-auto max-w-[var(--max-content)] rounded-3xl border border-[var(--border-default)] bg-white p-6 sm:p-8">
            <div className="mb-5 max-w-[var(--max-reading)]">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">Comparison</p>
              <h3 className="display-title mt-2 text-3xl font-black tracking-tight sm:text-4xl">A workflow replacement, not another search tab.</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-default)] text-left text-xs uppercase tracking-[0.16em] text-[var(--text-muted)]">
                    <th className="px-3 py-3">Capability</th>
                    <th className="px-3 py-3">Generic tools</th>
                    <th className="px-3 py-3">Neyma</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.map((row) => (
                    <tr key={row.label} className="border-b border-[var(--border-default)]/70 align-top">
                      <td className="px-3 py-3 font-semibold text-[var(--text-primary)]">{row.label}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{row.generic}</td>
                      <td className="px-3 py-3 text-[var(--text-primary)]">{row.neyma}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="px-4 py-8 sm:px-6 sm:py-12">
          <div className="mx-auto grid max-w-[var(--max-content)] gap-6 lg:grid-cols-2">
            <CardBlock title="Outcome visibility" text="Track contacted, won, and lost directly against diagnostics to build a true feedback loop for your targeting strategy." />
            <CardBlock title="Operational consistency" text="Standardize how your team researches, prioritizes, and briefs prospects with a repeatable command surface." />
          </div>
        </section>

        <section className="px-4 pb-12 pt-8 sm:px-6 sm:pb-16 sm:pt-12">
          <div className="mx-auto max-w-[var(--max-content)] rounded-3xl border border-[var(--border-default)] bg-white p-6 sm:p-8">
            <div className="mb-6">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">FAQ</p>
              <h3 className="display-title mt-2 text-3xl font-black tracking-tight sm:text-4xl">Questions teams ask before rolling out Neyma.</h3>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {faq.map((item) => (
                <div key={item.q} className="rounded-2xl border border-[var(--border-default)] p-4">
                  <p className="font-semibold text-[var(--text-primary)]">{item.q}</p>
                  <p className="mt-2 text-sm text-[var(--text-secondary)]">{item.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--border-default)] bg-white px-4 py-8 sm:px-6">
        <div className="mx-auto flex max-w-[var(--max-content)] flex-col gap-4 text-sm text-[var(--text-muted)] sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span className="font-semibold text-[var(--text-primary)]">Neyma</span> Revenue Intelligence Platform
          </div>
          <div className="flex items-center gap-5">
            <Link href="/ask" className="hover:text-[var(--text-primary)]">Ask Neyma</Link>
            <Link href="/territory/new" className="hover:text-[var(--text-primary)]">Territory</Link>
            <Link href="/diagnostic/new" className="hover:text-[var(--text-primary)]">New diagnostic</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function CardBlock({ title, text }: { title: string; text: string }) {
  return (
    <article className="rounded-3xl border border-[var(--border-default)] bg-white p-6">
      <h4 className="display-title text-2xl font-bold text-[var(--text-primary)]">{title}</h4>
      <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">{text}</p>
    </article>
  );
}
