"use client";

import { AuthGuard } from "@/lib/auth";
import Nav from "../components/Nav";
import Footer from "../components/Footer";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col">
        <Nav />
        <div className="flex-1">{children}</div>
        <Footer />
      </div>
    </AuthGuard>
  );
}
