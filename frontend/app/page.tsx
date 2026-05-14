"use client";
import { useEffect, useState, useCallback } from "react";
import { getFindings, getStats, Finding, Stats } from "@/lib/api";
import { FindingsTable } from "@/components/FindingsTable";
import { FindingDrawer } from "@/components/FindingDrawer";
import { StatsBar } from "@/components/StatsBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const TABS = [
  { value: "pending",     label: "Pending" },
  { value: "approved",    label: "Approved" },
  { value: "dismissed",   label: "Dismissed" },
  { value: "auto_posted", label: "Auto-posted" },
];

export default function FindingsPage() {
  const [tab, setTab] = useState("pending");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Finding | null>(null);

  const loadStats = useCallback(() => {
    getStats().then(setStats).catch(() => null);
  }, []);

  const load = useCallback((status: string) => {
    setLoading(true);
    setError(null);
    getFindings(status)
      .then(setFindings)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { load(tab); }, [tab, load]);

  function handleResolved(id: number) {
    setFindings((prev) => prev.filter((f) => f.id !== id));
    loadStats();
  }

  return (
    <main className="container mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Findings</h1>
        <p className="text-sm text-gray-500">Review and action AI-detected issues from your pull requests</p>
      </div>

      {stats && <StatsBar stats={stats} />}

      <Tabs value={tab} onValueChange={(v) => { setTab(v); setSelected(null); }}>
        <TabsList className="bg-white border border-gray-200">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value} className="text-sm">
              {t.label}
              {t.value === "pending" && stats?.pending ? (
                <span className="ml-1.5 bg-amber-100 text-amber-700 text-xs px-1.5 py-0.5 rounded-full font-medium">
                  {stats.pending}
                </span>
              ) : null}
            </TabsTrigger>
          ))}
        </TabsList>

        {TABS.map((t) => (
          <TabsContent key={t.value} value={t.value} className="mt-4">
            {loading && (
              <div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
                <p className="text-gray-400 text-sm">Loading…</p>
              </div>
            )}
            {error && <p className="text-red-500 text-sm py-4">Error: {error}</p>}
            {!loading && !error && (
              <FindingsTable
                findings={findings}
                showActions={t.value === "pending"}
                onSelect={setSelected}
                onResolved={handleResolved}
              />
            )}
          </TabsContent>
        ))}
      </Tabs>

      <FindingDrawer
        finding={selected}
        onClose={() => setSelected(null)}
        onResolved={handleResolved}
      />
    </main>
  );
}
