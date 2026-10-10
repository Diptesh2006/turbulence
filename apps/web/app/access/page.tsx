"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export default function AccessPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/demo-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        throw new Error(result?.detail ?? "Unable to verify invite code");
      }
      router.replace("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to verify invite code");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md items-center px-5 py-10">
      <form onSubmit={submit} className="w-full space-y-5">
        <div>
          <p className="metadata text-muted-foreground">TURBULENCE · PRIVATE DEMO</p>
          <h1 className="mt-3 text-2xl font-semibold">Enter your invite code</h1>
        </div>
        <label className="block space-y-2 text-sm font-medium" htmlFor="invite-code">
          Invite code
          <input
            id="invite-code"
            autoComplete="current-password"
            autoFocus
            required
            type="password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            className="h-10 w-full rounded-md border border-input bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? "Checking..." : "Continue"}
        </Button>
      </form>
    </main>
  );
}
