"use client";

import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-[calc(100vh-8rem)] bg-zinc-50 text-zinc-900">
      <main className="mx-auto max-w-2xl px-6 py-10">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mb-8 text-sm text-zinc-500">Manage your account and preferences</p>

        {/* Account */}
        <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-zinc-500">Account</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-zinc-700">Name</label>
              <input
                type="text"
                value={user?.name ?? ""}
                readOnly
                className="w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-zinc-700">Email</label>
              <input
                type="email"
                value={user?.email ?? ""}
                readOnly
                className="w-full rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600"
              />
            </div>
          </div>
        </section>

        {/* API Keys placeholder */}
        <section className="mt-6 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-zinc-500">API Keys</h2>
          <p className="text-sm text-zinc-500">API key management will be available in a future update.</p>
          <div className="mt-4 rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 py-8 text-center text-sm text-zinc-400">
            No API keys yet
          </div>
        </section>

        {/* Plan placeholder */}
        <section className="mt-6 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-zinc-500">Plan & Usage</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-zinc-900">Free Plan</p>
              <p className="mt-1 text-sm text-zinc-500">Unlimited diagnostics during beta</p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">Active</span>
          </div>
        </section>
      </main>
    </div>
  );
}
