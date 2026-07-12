export function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number | null | undefined;
  detail?: string;
}) {
  return (
    <div className="panel p-4">
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-normal">
        {value ?? "n/a"}
      </div>
      {detail ? <div className="metadata mt-2 text-muted-foreground">{detail}</div> : null}
    </div>
  );
}

