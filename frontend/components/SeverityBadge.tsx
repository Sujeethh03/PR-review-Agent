"use client";

const styles: Record<string, string> = {
  high:   "bg-red-100 text-red-700 ring-1 ring-red-200",
  medium: "bg-amber-100 text-amber-700 ring-1 ring-amber-200",
  low:    "bg-blue-100 text-blue-700 ring-1 ring-blue-200",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ${styles[severity] ?? "bg-gray-100 text-gray-600"}`}>
      {severity.toUpperCase()}
    </span>
  );
}
