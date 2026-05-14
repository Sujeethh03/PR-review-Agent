"use client";

interface Stats {
  total: number;
  pending: number;
  approved: number;
  auto_posted: number;
  dismissed: number;
}

const cards = [
  {
    key: "total" as const,
    label: "Total Findings",
    color: "text-gray-800",
    bg: "bg-white",
    border: "border-gray-200",
    dot: "bg-gray-400",
  },
  {
    key: "pending" as const,
    label: "Pending Review",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    dot: "bg-amber-400",
  },
  {
    key: "auto_posted" as const,
    label: "Auto-posted",
    color: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    dot: "bg-green-400",
  },
  {
    key: "approved" as const,
    label: "Approved",
    color: "text-indigo-700",
    bg: "bg-indigo-50",
    border: "border-indigo-200",
    dot: "bg-indigo-400",
  },
];

export function StatsBar({ stats }: { stats: Stats }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div
          key={c.key}
          className={`rounded-xl border ${c.border} ${c.bg} px-5 py-4 flex items-center gap-4`}
        >
          <div className={`w-2.5 h-2.5 rounded-full ${c.dot} shrink-0`} />
          <div>
            <p className={`text-2xl font-bold ${c.color}`}>{stats[c.key]}</p>
            <p className="text-xs text-gray-500 font-medium">{c.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
