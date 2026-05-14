"use client";
import { useEffect, useState, useCallback } from "react";
import { getFindings, Finding } from "@/lib/api";
import { FindingsTable } from "@/components/FindingsTable";
import { FindingDrawer } from "@/components/FindingDrawer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Link from "next/link";

const TABS = [
  { value: "pending",    label: "Pending" },
  { value: "approved",   label: "Approved" },
  { value: "dismissed",  label: "Dismissed" },
  { value: "auto_posted",label: "Auto-posted" },
];

export default function FindingsPage() {
  const [tab, setTab] = useState("pending");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Finding | null>(null);

  const load = useCallback((status: string) => {
    setLoading(true);
    setError(null);
    getFindings(status)
      .then(setFindings)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(tab); }, [tab, load]);

  function handleResolved(id: number) {
    setFindings((prev) => prev.filter((f) => f.id !== id));
  }

  return (
    <main className="container mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Code Review Agent</h1>
          <p className="text-muted-foreground">AI-detected findings from your pull requests</p>
        </div>
        <Link href="/reviews" className="text-sm text-muted-foreground underline">
          View PR Reviews →
        </Link>
      </div>

      <Tabs value={tab} onValueChange={(v) => { setTab(v); setSelected(null); }}>
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>
          ))}
        </TabsList>

        {TABS.map((t) => (
          <TabsContent key={t.value} value={t.value}>
            {loading && <p className="text-muted-foreground py-8 text-center">Loading…</p>}
            {error   && <p className="text-destructive py-4">Error: {error}</p>}
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
