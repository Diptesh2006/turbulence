"use client";

import { Activity, BarChart3, GitCompare, Home, PlaneTakeoff, ScrollText, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Overview", icon: Home },
  { href: "/scenarios", label: "Provider scenarios", icon: ScrollText },
  { href: "/agent-safety", label: "Agent Safety Lab", icon: ShieldAlert },
  { href: "/agent-safety/runs", label: "Safety runs", icon: Activity },
  { href: "/agent-safety/policies", label: "Safety policies", icon: ScrollText },
  { href: "/simulations/new", label: "New provider run", icon: PlaneTakeoff },
  { href: "/compare", label: "Compare", icon: GitCompare },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-white lg:block">
        <div className="border-b px-5 py-5">
          <Link href="/" className="block">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-foreground text-background">
                <Activity className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <div className="text-base font-semibold">Turbulence</div>
                <div className="text-xs text-muted-foreground">AI Flight Simulator</div>
              </div>
            </div>
          </Link>
          <p className="mt-4 text-sm leading-5 text-muted-foreground">
            Crash-test your LLM stack before production.
          </p>
        </div>
        <nav className="space-y-1 px-3 py-4" aria-label="Primary">
          {navItems.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                  active
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="absolute bottom-0 w-full border-t p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            Operations console
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b bg-white/95 backdrop-blur">
          <div className="flex min-h-14 items-center justify-between px-4 lg:px-6">
            <div>
              <div className="text-sm font-semibold lg:hidden">Turbulence</div>
              <div className="hidden text-sm text-muted-foreground lg:block">
                AI Flight Simulator
              </div>
            </div>
            <Link
              href="/simulations/new"
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
            >
              Start simulation
            </Link>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t px-2 py-2 lg:hidden" aria-label="Mobile">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "whitespace-nowrap rounded-md px-3 py-1.5 text-sm",
                  pathname === item.href ? "bg-foreground text-background" : "text-muted-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="px-4 py-6 lg:px-6">{children}</main>
      </div>
    </div>
  );
}

