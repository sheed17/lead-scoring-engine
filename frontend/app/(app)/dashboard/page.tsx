"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { deleteDiagnostic, getOutcomesSummary, getRecentTerritoryScans, listDiagnostics } from "@/lib/api";
import type { DiagnosticListItem, OutcomesSummaryResponse, TerritoryScanListItem } from "@/lib/types";
import Button from "@/app/components/ui/Button";
import Input from "@/app/components/ui/Input";
import { Card, CardBody, CardHeader } from "@/app/components/ui/Card";
import Badge from "@/app/components/ui/Badge";
import { Table, THead, TH, TR, TD } from "@/app/components/ui/Table";
import EmptyState from "@/app/components/ui/EmptyState";
import { Skeleton } from "@/app/components/ui/Skeleton";

const PAGE_SIZE = 10;

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border-default)] bg-white px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{label}</p>
      <p className="display-title mt-1 text-2xl font-bold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

export default function DashboardPage() {
  const [items, setItems] = useState<DiagnosticListItem[]>([]);
  const [scans, setScans] = useState<TerritoryScanListItem[]>([]);
  const [summary, setSummary] = useState<OutcomesSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [diag, recent, out] = await Promise.all([
          listDiagnostics(200, 0),
          getRecentTerritoryScans(10),
          getOutcomesSummary().catch(() => null),
        ]);
        setItems(diag.items);
        setScans(recent.items);
        setSummary(out);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((d) => `${d.business_name} ${d.city} ${d.state || ""} ${d.opportunity_profile || ""}`.toLowerCase().includes(q));
  }, [items, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const cities = new Set(items.map((d) => d.city)).size;
  const totalUpside = items.reduce((acc, d) => {
    const m = d.modeled_revenue_upside?.match(/\$(\d[\d,]*)/);
    return m ? acc + parseInt(m[1].replace(/,/g, ""), 10) : acc;
  }, 0);

  async function onDelete(id: number) {
    if (!confirm("Delete this diagnostic?")) return;
    await deleteDiagnostic(id);
    setItems((prev) => prev.filter((x) => x.id !== id));
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[var(--max-content)] space-y-4">
        <Skeleton className="h-28" />
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[var(--max-content)] space-y-4">
      <Card className="overflow-hidden">
        <CardBody className="bg-gradient-to-r from-[#0f172a] via-[#13233f] to-[#0b3f5f] p-6 text-white sm:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-2xl">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">Operating Console</p>
              <h1 className="display-title mt-2 text-3xl font-black leading-tight sm:text-5xl">Run your pipeline with one clear next action.</h1>
              <p className="mt-3 text-sm text-slate-200 sm:text-base">Start with territory scans to prioritize markets, then use Ask Neyma for precise prospect intent queries.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href="/territory/new"><Button variant="primary" className="h-11 rounded-full bg-white px-5 text-slate-900 hover:bg-slate-100">Run territory scan</Button></Link>
              <Link href="/ask"><Button className="h-11 rounded-full border-white/20 bg-white/10 px-5 text-white hover:bg-white/15">Ask Neyma</Button></Link>
            </div>
          </div>
        </CardBody>
      </Card>

      {summary && (
        <Card>
          <CardHeader title="Pipeline Status" subtitle="Latest outreach state across all briefs." />
          <CardBody className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <MiniStat label="Contacted" value={String(summary.contacted || 0)} />
            <MiniStat label="Won" value={String(summary.closed_won || 0)} />
            <MiniStat label="Lost" value={String(summary.closed_lost || 0)} />
            <MiniStat label="Not contacted" value={String(summary.not_contacted || 0)} />
            <MiniStat label="Won (30d)" value={String(summary.closed_this_month || 0)} />
          </CardBody>
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.15fr_2fr]">
        <Card>
          <CardHeader title="Next Best Action" subtitle="Single focus for this session." />
          <CardBody className="space-y-4">
            <div className="rounded-2xl border border-[var(--border-default)] bg-[#f7fbff] p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">Run a fresh territory scan for your next market.</p>
              <p className="mt-1 text-sm text-[var(--text-muted)]">Then open Ask Neyma for exact filtering once the market shortlist is in place.</p>
            </div>
            <Link href="/territory/new"><Button variant="primary" className="w-full">Start with territory scan</Button></Link>
            <Link href="/diagnostic/new" className="app-link block text-sm font-medium">Or run a single diagnostic</Link>
          </CardBody>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <MiniStat label="Total diagnostics" value={String(items.length)} />
          <MiniStat label="Upside identified" value={totalUpside ? `$${totalUpside.toLocaleString()}` : "—"} />
          <MiniStat label="Cities covered" value={String(cities)} />
          <MiniStat label="Added this month" value={String(items.filter((d) => { const dt = new Date(d.created_at); const n = new Date(); return dt.getMonth() === n.getMonth() && dt.getFullYear() === n.getFullYear(); }).length)} />
        </div>
      </div>

      <Card>
        <CardHeader title="Your Briefs" subtitle="Search and work the current pipeline." action={<div className="w-72"><Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search business, city, opportunity..." /></div>} />
        {items.length === 0 ? (
          <CardBody>
            <EmptyState
              title="No diagnostics yet"
              description="Run an Ask query or create a new diagnostic to start building pipeline."
              action={<Link href="/territory/new"><Button variant="primary">Run territory</Button></Link>}
            />
          </CardBody>
        ) : (
          <>
            <Table>
              <THead><tr><TH>Business</TH><TH>City</TH><TH>Opportunity</TH><TH>Upside</TH><TH>Date</TH><TH className="text-right">Actions</TH></tr></THead>
              <tbody>
                {pageItems.map((item) => (
                  <TR key={item.id}>
                    <TD className="font-medium text-[var(--text-primary)]">{item.business_name}</TD>
                    <TD>{item.city}{item.state ? `, ${item.state}` : ""}</TD>
                    <TD>{item.opportunity_profile ? <Badge>{item.opportunity_profile}</Badge> : "—"}</TD>
                    <TD>{item.modeled_revenue_upside || "—"}</TD>
                    <TD>{fmtDate(item.created_at)}</TD>
                    <TD className="text-right">
                      <Link href={`/diagnostic/${item.id}`} className="app-link mr-3 font-medium">View brief</Link>
                      <button onClick={() => void onDelete(item.id)} className="text-rose-600 hover:underline">Delete</button>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
            {totalPages > 1 && (
              <CardBody className="flex items-center justify-between border-t border-[var(--border-default)]">
                <p className="text-sm text-[var(--text-muted)]">
                  Showing {page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
                </p>
                <div className="flex gap-2">
                  <Button disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>Previous</Button>
                  <Button disabled={page >= totalPages - 1} onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}>Next</Button>
                </div>
              </CardBody>
            )}
          </>
        )}
      </Card>

      {scans.length > 0 && (
        <Card>
          <CardHeader title="Recent Territory Scans" subtitle="Jump back to completed and running scans." />
          <Table>
            <THead><tr><TH>Market</TH><TH>Vertical</TH><TH>Prospects</TH><TH>Status</TH><TH>Date</TH><TH className="text-right">Open</TH></tr></THead>
            <tbody>
              {scans.map((s) => (
                <TR key={s.id}>
                  <TD>{s.city || "—"}{s.state ? `, ${s.state}` : ""}</TD>
                  <TD>{s.vertical || "—"}</TD>
                  <TD>{s.prospects_count ?? Number((s.summary?.accepted as number) || 0)}</TD>
                  <TD><Badge tone={s.status === "completed" ? "success" : "muted"}>{s.status}</Badge></TD>
                  <TD>{fmtDate(s.created_at)}</TD>
                  <TD className="text-right"><Link href={`/territory/${s.id}`} className="app-link font-medium">View results</Link></TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
