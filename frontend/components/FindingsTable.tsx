"use client";
import { useState } from "react";
import { Finding, approveFinding, dismissFinding } from "@/lib/api";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";

export function FindingsTable({ initial }: { initial: Finding[] }) {
  const [findings, setFindings] = useState(initial);
  const [loading, setLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(id: number, action: "approve" | "dismiss") {
    setLoading(id);
    setError(null);
    try {
      const updated = action === "approve"
        ? await approveFinding(id)
        : await dismissFinding(id);
      setFindings((prev) => prev.filter((f) => f.id !== updated.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setLoading(null);
    }
  }

  if (findings.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No pending findings</CardTitle>
          <CardDescription>All findings have been reviewed.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pending Findings</CardTitle>
        <CardDescription>{findings.length} finding(s) awaiting review</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <p className="text-sm text-destructive">Error: {error}</p>
        )}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Severity</TableHead>
              <TableHead>File</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              <TableHead className="text-center">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {findings.map((f) => (
              <TableRow key={f.id}>
                <TableCell><SeverityBadge severity={f.severity} /></TableCell>
                <TableCell className="font-mono text-sm">
                  {f.file}:{f.line_start}
                </TableCell>
                <TableCell>
                  <div className="font-medium">{f.title}</div>
                  <div className="text-sm text-muted-foreground line-clamp-2">
                    {f.description}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{f.agent}</Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {(f.specialist_conf * 100).toFixed(0)}%
                </TableCell>
                <TableCell>
                  <div className="flex gap-2 justify-center">
                    <Button
                      size="sm"
                      onClick={() => handle(f.id, "approve")}
                      disabled={loading !== null}
                    >
                      {loading === f.id ? "Posting…" : "Approve"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handle(f.id, "dismiss")}
                      disabled={loading !== null}
                    >
                      {loading === f.id ? "…" : "Dismiss"}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
