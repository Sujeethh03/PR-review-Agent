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
      const updated = action === "approve"
        ? await approveFinding(id)
        : await dismissFinding(id);
      onResolved(updated.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setLoading(null);
    }
  }

  if (findings.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No findings</CardTitle>
          <CardDescription>Nothing in this category yet.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{findings.length} finding{findings.length !== 1 ? "s" : ""}</CardTitle>
        {error && <p className="text-sm text-destructive">Error: {error}</p>}
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Severity</TableHead>
              <TableHead>File</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              {showActions && <TableHead className="text-center">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {findings.map((f) => (
              <TableRow
                key={f.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => onSelect(f)}
              >
                <TableCell><SeverityBadge severity={f.severity} /></TableCell>
                <TableCell className="font-mono text-sm">
                  {f.file}:{f.line_start}
                </TableCell>
                <TableCell>
                  <div className="font-medium">{f.title}</div>
                  <div className="text-sm text-muted-foreground line-clamp-1">
                    {f.description}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{f.agent}</Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {(f.specialist_conf * 100).toFixed(0)}%
                </TableCell>
                {showActions && (
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-2 justify-center">
                      <Button
                        size="sm"
                        onClick={(e) => handle(e, f.id, "approve")}
                        disabled={loading !== null}
                      >
                        {loading === f.id ? "Posting…" : "Approve"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => handle(e, f.id, "dismiss")}
                        disabled={loading !== null}
                      >
                        {loading === f.id ? "…" : "Dismiss"}
                      </Button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
