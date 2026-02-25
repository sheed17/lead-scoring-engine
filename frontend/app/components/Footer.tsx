import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-white px-6 py-8">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 sm:flex-row">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-sm font-semibold text-zinc-900">Neyma</Link>
          <span className="text-xs text-zinc-400">Lead Intelligence Platform</span>
        </div>
        <div className="flex items-center gap-6 text-xs text-zinc-500">
          <Link href="/dashboard" className="hover:text-zinc-700">Dashboard</Link>
          <Link href="/diagnostic/new" className="hover:text-zinc-700">New Diagnostic</Link>
          <Link href="/settings" className="hover:text-zinc-700">Settings</Link>
        </div>
      </div>
    </footer>
  );
}
