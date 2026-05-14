const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Finding {
  id: number;
  finding_hash: string;
  pr_review_id: number;
  agent: "bug" | "security" | "pattern";
  file: string;
  line_start: number;
  line_end: number;
  severity: "high" | "medium" | "low";
  category: string;
  title: string;
  description: string;
  suggestion: string;
  specialist_conf: number;
  route: "auto" | "queue" | "digest";
  status: "pending" | "approved" | "dismissed" | "auto_posted" | "digest";
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  // joined from pr_reviews
  owner?: string;
  repo_name?: string;
  pr_number?: number;
  head_sha?: string;
}

export interface Review {
  id: number;
  owner: string;
  repo_name: string;
  pr_number: number;
  head_sha: string;
  created_at: string;
  total: number;
  pending: number;
  approved: number;
  dismissed: number;
}

export async function getFindings(status?: string): Promise<Finding[]> {
  const url = status ? `${BASE}/findings?status=${status}` : `${BASE}/findings`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch findings");
  return res.json();
}

export async function getFinding(id: number): Promise<Finding> {
  const res = await fetch(`${BASE}/findings/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch finding");
  return res.json();
}

export async function getReviews(): Promise<Review[]> {
  const res = await fetch(`${BASE}/reviews`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch reviews");
  return res.json();
}

export async function approveFinding(id: number): Promise<Finding> {
  const res = await fetch(`${BASE}/findings/${id}/approve`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolved_by: "dashboard" }),
  });
  if (!res.ok) throw new Error("Failed to approve finding");
  return res.json();
}

export async function dismissFinding(id: number): Promise<Finding> {
  const res = await fetch(`${BASE}/findings/${id}/dismiss`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolved_by: "dashboard" }),
  });
  if (!res.ok) throw new Error("Failed to dismiss finding");
  return res.json();
}
