"use client";

import { AuthGuard } from "@/lib/auth";
import AppShell from "../components/AppShell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
