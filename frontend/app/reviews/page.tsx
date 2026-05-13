"use client";
import { useEffect, useState } from "react";
import { getReviews, Review } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">PR Reviews</h1>
          <p className="text-muted-foreground">All pull requests analysed by the agent</p>
        </div>
        <Link href="/" className="text-sm text-muted-foreground underline">
          ← Pending Findings
        </Link>
      </div>

      {loading && <p className="text-muted-foreground">Loading...</p>}
      {error && <p className="text-destructive">Error: {error}</p>}
      {!loading && !error && reviews.length === 0 && (
        <Card>
          <CardHeader><CardTitle>No reviews yet</CardTitle></CardHeader>
        </Card>
      )}
      {!loading && !error && reviews.length > 0 && (
        <div className="space-y-4">
          {reviews.map((r) => (
            <Card key={r.id}>
              <CardContent className="pt-6 flex items-center justify-between">
                <div>
                  <p className="font-semibold">
                    {r.owner}/{r.repo_name} — PR #{r.pr_number}
                  </p>
                  <p className="text-sm text-muted-foreground font-mono">
                    {r.head_sha.slice(0, 7)} · {new Date(r.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Badge variant="outline">{r.total} total</Badge>
                  <Badge variant="default">{r.pending} pending</Badge>
                  <Badge variant="secondary">{r.approved} approved</Badge>
                  <Badge variant="outline">{r.dismissed} dismissed</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </main>
  );
}
