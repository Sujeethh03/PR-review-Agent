"use client";
import { useEffect, useState } from "react";
import { getReviews, Review } from "@/lib/api";

const statusDot: Record<string, string> = {
  pending:    "bg-amber-400",
  approved:   "bg-indigo-400",
  dismissed:  "bg-gray-300",
  auto_posted:"bg-green-400",
};

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReviews()
      .then(setReviews)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="container mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">PR Reviews</h1>
        <p className="text-sm text-gray-500">All pull requests analysed by the agent</p>
      </div>

      {loading && (
        <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
          <p className="text-gray-400 text-sm">Loading…</p>
        </div>
      )}
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {!loading && !error && reviews.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-200 bg-white py-16 text-center">
          <p className="text-gray-400 text-sm">No reviews yet</p>
        </div>
      )}

      {!loading && !error && reviews.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                <th className="text-left px-4 py-3 font-medium text-gray-500">Repository / PR</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 hidden md:table-cell">Commit</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500 hidden md:table-cell">Date</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Findings</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {reviews.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">
                      {r.owner}/{r.repo_name}
                    </p>
                    <p className="text-xs text-gray-400">PR #{r.pr_number}</p>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500 hidden md:table-cell">
                    {r.head_sha.slice(0, 7)}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 hidden md:table-cell">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2 flex-wrap">
                      {[
                        { key: "total",    label: "total",    style: "bg-gray-100 text-gray-600" },
                        { key: "pending",  label: "pending",  style: "bg-amber-100 text-amber-700" },
                        { key: "approved", label: "approved", style: "bg-indigo-100 text-indigo-700" },
                        { key: "dismissed",label: "dismissed",style: "bg-gray-100 text-gray-500" },
                      ].map(({ key, label, style }) => (
                        <span key={key} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${style}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${statusDot[key] ?? "bg-gray-300"}`} />
                          {r[key as keyof Review]} {label}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
