"use client";
import { useState } from "react";
import { Finding, approveFinding, dismissFinding } from "@/lib/api";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";

const severityBorder: Record<string, string> = {
  high:   "border-l-red-400",
  medium: "border-l-amber-400",
  low:    "border-l-blue-400",
};

const routeBadge: Record<string, string> = {
  auto:   "bg-green-100 text-green-700",
  queue:  "bg-amber-100 text-amber-700",
  digest: "bg-gray-100 text-gray-500",
};

interface Props {
  findings: Finding[];
  showActions: boolean;
  onSelect: (f: Finding) => void;
  onResolved: (id: number) => void;
}

export function FindingsTable({ findings, showActions, onSelect, onResolved }: Props) {
  const [loading, setLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(e: React.MouseEvent, id: number, action: "approve" | "dismiss") {
    e.stopPropagation();
    setLoading(id);
    setError(null);
    try {
      const updated = action === "approve" ? await approveFinding(id) : await dismissFinding(id);
      onResolved(updated.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setLoading(null);
    }
  }

  if (findings.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-white py-16 text-center">
        <p className="text-gray-400 text-sm">No findings in this category</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
      {error && (
        <div className="px-4 py-2 bg-red-50 border-b border-red-100 text-sm text-red-600">
          {error}
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50/80">
            <th className="text-left px-4 py-3 font-medium text-gray-500 w-4" />
            <th className="text-left px-4 py-3 font-medium text-gray-500">Title</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 hidden md:table-cell">File</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 hidden lg:table-cell">Agent</th>
            <th className="text-left px-4 py-3 font-medium text-gray-500 hidden lg:table-cell">Route</th>
            <th className="text-right px-4 py-3 font-medium text-gray-500">Conf.</th>
            {showActions && <th className="px-4 py-3" />}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {findings.map((f) => (
            <tr
              key={f.id}
              onClick={() => onSelect(f)}
              className={`border-l-4 ${severityBorder[f.severity] ?? "border-l-gray-200"} hover:bg-gray-50 cursor-pointer transition-colors`}
            >
              <td className="px-4 py-3">
                <SeverityBadge severity={f.severity} />
              </td>
              <td className="px-4 py-3">
                <p className="font-medium text-gray-900">{f.title}</p>
                <p className="text-xs text-gray-400 line-clamp-1 mt-0.5">{f.description}</p>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-gray-500 hidden md:table-cell">
                {f.file}:{f.line_start}
              </td>
              <td className="px-4 py-3 hidden lg:table-cell">
                <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                  {f.agent}
                </span>
              </td>
              <td className="px-4 py-3 hidden lg:table-cell">
                <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${routeBadge[f.route] ?? ""}`}>
                  {f.route}
                </span>
              </td>
              <td className="px-4 py-3 text-right font-mono text-xs text-gray-500">
                {(f.specialist_conf * 100).toFixed(0)}%
              </td>
              {showActions && (
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  <div className="flex gap-2 justify-end">
                    <Button
                      size="sm"
                      className="h-7 px-3 text-xs"
                      onClick={(e) => handle(e, f.id, "approve")}
                      disabled={loading !== null}
                    >
                      {loading === f.id ? "Posting…" : "Approve"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-3 text-xs"
                      onClick={(e) => handle(e, f.id, "dismiss")}
                      disabled={loading !== null}
                    >
                      {loading === f.id ? "…" : "Dismiss"}
                    </Button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
