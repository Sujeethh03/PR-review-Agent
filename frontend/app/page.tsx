"use client";
import { useEffect, useState } from "react";
import { getFindings, Finding } from "@/lib/api";
import { FindingsTable } from "@/components/FindingsTable";
import Link from "next/link";

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFindings()
      .then(setFindings)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="container mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Code Review Agent</h1>
          <p className="text-muted-foreground">Pending findings awaiting human review</p>
        </div>
        <Link href="/reviews" className="text-sm text-muted-foreground underline">
          View PR Reviews →
        </Link>
      </div>
      {loading && <p className="text-muted-foreground">Loading...</p>}
      {error && <p className="text-destructive">Error: {error}</p>}
      {!loading && !error && <FindingsTable initial={findings} />}
    </main>
  );
}
