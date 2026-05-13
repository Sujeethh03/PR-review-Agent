"use client";
import { Badge } from "@/components/ui/badge";

const variants: Record<string, "destructive" | "default" | "secondary"> = {
  high:   "destructive",
  medium: "default",
  low:    "secondary",
};

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge variant={variants[severity] ?? "secondary"}>
      {severity.toUpperCase()}
    </Badge>
  );
}
