export function StatusTile({
  label,
  value,
  truncate,
  statusDot,
}: {
  label: string;
  value: string;
  truncate?: boolean;
  statusDot?: "green" | "red";
}) {
  return (
    <div className="rounded-md border bg-muted/40 px-3 py-2">
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-0.5">
        {label}
      </p>
      <div className="flex items-center gap-1.5">
        {statusDot && (
          <span
            className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${
              statusDot === "green" ? "bg-green-500" : "bg-red-400"
            }`}
          />
        )}
        <p
          className={`text-sm font-medium tabular-nums ${
            truncate ? "truncate" : ""
          }`}
          title={truncate ? value : undefined}
        >
          {value}
        </p>
      </div>
    </div>
  );
}