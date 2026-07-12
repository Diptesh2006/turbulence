import { AlertCircle, Inbox } from "lucide-react";

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-label="Loading">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="panel flex min-h-40 flex-col items-center justify-center p-6 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
      <h3 className="mt-3 text-sm font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}

export function ErrorState({ title = "Request failed", error }: { title?: string; error: Error }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <div className="flex gap-2">
        <AlertCircle className="mt-0.5 h-4 w-4" aria-hidden="true" />
        <div>
          <div className="font-semibold">{title}</div>
          <div className="mt-1">{error.message}</div>
        </div>
      </div>
    </div>
  );
}

