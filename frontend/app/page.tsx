"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import Footer from "./components/Footer";

const features = [
  {
    title: "Competitive Intelligence",
    desc: "Automatically sample nearby competitors, compare review authority, ratings, and market density to surface your prospect's true position.",
  },
  {
    title: "Revenue Modeling",
    desc: "Model revenue upside from missing high-ticket service pages, schema gaps, and conversion infrastructure weaknesses.",
  },
  {
    title: "Intervention Plans",
    desc: "Get a prioritized 3-step action plan with time-to-signal estimates so you know exactly what to pitch and when results show.",
  },
];

const steps = [
  { num: "01", title: "Enter a business", desc: "Name, city, and optional website — that's all we need." },
  { num: "02", title: "Pipeline runs", desc: "We resolve the business, pull competitor data, scan their site, and run 40+ signal checks." },
  { num: "03", title: "Get your brief", desc: "A full Revenue Intelligence Brief with opportunity profile, risk flags, and actionable next steps." },
];

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-white text-zinc-900">
      {/* Nav */}
      <header className="border-b border-zinc-100 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <Link href="/" className="text-xl font-bold tracking-tight">Neyma</Link>
          <div className="flex items-center gap-3">
            {user ? (
              <Link href="/dashboard" className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">
                Dashboard
              </Link>
            ) : (
              <>
                <Link href="/login" className="rounded-lg px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900">
                  Log in
                </Link>
                <Link href="/register" className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800">
                  Get started
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 py-24 text-center">
        <div className="mx-auto max-w-2xl">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Turn any business name into a<br />
            <span className="text-emerald-600">revenue intelligence brief</span>
          </h1>
          <p className="mx-auto mt-6 max-w-lg text-lg text-zinc-600">
            Enter a practice name and city. Neyma runs competitive analysis, scans their digital presence, and delivers a full diagnostic with modeled revenue upside and a prioritized intervention plan.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            <Link
              href={user ? "/diagnostic/new" : "/register"}
              className="rounded-lg bg-zinc-900 px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-zinc-800"
            >
              Run your first diagnostic
            </Link>
            <a href="#how-it-works" className="rounded-lg px-6 py-3 text-sm font-medium text-zinc-600 hover:text-zinc-900">
              How it works
            </a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-zinc-100 bg-zinc-50 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-12 text-center text-2xl font-semibold tracking-tight">What you get from every diagnostic</h2>
          <div className="grid gap-8 md:grid-cols-3">
            {features.map((f) => (
              <div key={f.title} className="rounded-xl border border-zinc-200 bg-white p-6">
                <h3 className="mb-2 font-semibold text-zinc-900">{f.title}</h3>
                <p className="text-sm leading-relaxed text-zinc-600">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="px-6 py-20">
        <div className="mx-auto max-w-3xl">
          <h2 className="mb-12 text-center text-2xl font-semibold tracking-tight">How it works</h2>
          <div className="space-y-8">
            {steps.map((s) => (
              <div key={s.num} className="flex gap-6">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-zinc-900 text-sm font-bold text-white">
                  {s.num}
                </div>
                <div>
                  <h3 className="font-semibold text-zinc-900">{s.title}</h3>
                  <p className="mt-1 text-sm text-zinc-600">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-zinc-100 bg-zinc-50 px-6 py-20 text-center">
        <div className="mx-auto max-w-xl">
          <h2 className="text-2xl font-semibold tracking-tight">Ready to start scoring leads?</h2>
          <p className="mt-3 text-sm text-zinc-600">
            No credit card required. Run your first diagnostic in under 2 minutes.
          </p>
          <Link
            href={user ? "/diagnostic/new" : "/register"}
            className="mt-8 inline-block rounded-lg bg-zinc-900 px-6 py-3 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Get started free
          </Link>
        </div>
      </section>

      <Footer />
    </div>
  );
}
