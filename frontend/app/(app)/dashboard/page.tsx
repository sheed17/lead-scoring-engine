"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { listDiagnostics, deleteDiagnostic } from "@/lib/api";
import type { DiagnosticListItem } from "@/lib/types";

const PAGE_SIZE = 10;

export default function DashboardPage() {
  const [items, setItems] = useState<DiagnosticListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  async function load() {
    setLoading(true);
    try {
      const data = await listDiagnostics(200, 0);
      setItems(data.items);
      setTotal(data.total);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (d) =>
        d.business_name.toLowerCase().includes(q) ||
        d.city.toLowerCase().includes(q) ||
        (d.state ?? "").toLowerCase().includes(q) ||
        (d.opportunity_profile ?? "").toLowerCase().includes(q),
    );
  }, [items, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  useEffect(() => { setPage(0); }, [search]);

  async function handleDelete(id: number) {
    if (!confirm("Delete this diagnostic?")) return;
    try {
      await deleteDiagnostic(id);
      setItems((prev) => prev.filter((d) => d.id !== id));
      setTotal((t) => t - 1);
    } catch {
      /* ignore */
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  const totalUpside = items.reduce((acc, d) => {
    if (!d.modeled_revenue_upside) return acc;
    const match = d.modeled_revenue_upside.match(/\$(\d[\d,]*)/);
    if (match) return acc + parseInt(match[1].replace(/,/g, ""), 10);
    return acc;
  }, 0);

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-zinc-50 text-zinc-900">
      <main className="mx-auto max-w-5xl px-6 py-10">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
            <p className="mt-1 text-sm text-zinc-500">{total} diagnostic{total !== 1 ? "s" : ""} saved</p>
          </div>
          <Link
            href="/diagnostic/new"
            className="rounded-lg bg-zinc-900 px-4 py-2 text-center text-sm font-medium text-white transition hover:bg-zinc-800"
          >
            New diagnostic
          </Link>
        </div>

        {/* Stats row */}
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total Diagnostics" value={String(total)} />
          <StatCard label="Total Upside Identified" value={totalUpside > 0 ? `$${totalUpside.toLocaleString()}` : "—"} />
          <StatCard label="Cities Covered" value={String(new Set(items.map((d) => d.city)).size)} />
          <StatCard label="This Month" value={String(items.filter((d) => { const dt = new Date(d.created_at); const now = new Date(); return dt.getMonth() === now.getMonth() && dt.getFullYear() === now.getFullYear(); }).length)} />
        </div>

        {/* Search */}
        <div className="mb-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by business, city, or opportunity…"
            className="w-full rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 sm:max-w-sm"
          />
        </div>

        {loading ? (
          <div className="py-20 text-center text-sm text-zinc-400">Loading…</div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-300 bg-white py-20 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100 text-zinc-400">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 2v20M2 12h20" /></svg>
            </div>
            <p className="text-zinc-600 font-medium">No diagnostics yet</p>
            <p className="mt-1 text-sm text-zinc-500">Run your first diagnostic to get started</p>
            <Link href="/diagnostic/new" className="mt-4 inline-block rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">
              Run diagnostic
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-zinc-200 bg-white py-12 text-center">
            <p className="text-sm text-zinc-500">No results for &ldquo;{search}&rdquo;</p>
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm md:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-100 bg-zinc-50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                    <th className="px-4 py-3">Business</th>
                    <th className="px-4 py-3">City</th>
                    <th className="px-4 py-3">Opportunity</th>
                    <th className="px-4 py-3">Upside</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((item) => (
                    <tr key={item.id} className="border-b border-zinc-50 transition hover:bg-zinc-50/50">
                      <td className="px-4 py-3 font-medium">
                        <Link href={`/diagnostic/${item.id}`} className="hover:underline">
                          {item.business_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-zinc-600">{item.city}{item.state ? `, ${item.state}` : ""}</td>
                      <td className="px-4 py-3">
                        {item.opportunity_profile ? (
                          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                            {item.opportunity_profile}
                          </span>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-600">{item.modeled_revenue_upside || "—"}</td>
                      <td className="px-4 py-3 text-zinc-500">{formatDate(item.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <Link href={`/diagnostic/${item.id}`} className="mr-3 text-zinc-600 hover:text-zinc-900">
                          View
                        </Link>
                        <button onClick={() => handleDelete(item.id)} className="text-red-500 hover:text-red-700">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="space-y-3 md:hidden">
              {pageItems.map((item) => (
                <Link
                  key={item.id}
                  href={`/diagnostic/${item.id}`}
                  className="block rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition hover:border-zinc-300"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-zinc-900">{item.business_name}</p>
                      <p className="mt-0.5 text-sm text-zinc-500">{item.city}{item.state ? `, ${item.state}` : ""}</p>
                    </div>
                    {item.opportunity_profile && (
                      <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                        {item.opportunity_profile}
                      </span>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
                    <span>{item.modeled_revenue_upside || "—"}</span>
                    <span>{formatDate(item.created_at)}</span>
                  </div>
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between">
                <p className="text-sm text-zinc-500">
                  Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-50 disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-50 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-zinc-900">{value}</p>
    </div>
  );
}
