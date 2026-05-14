"use client";
import { Finding, approveFinding, dismissFinding } from "@/lib/api";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";

interface Props {
  finding: Finding | null;
  onClose: () => void;
  onResolved: (id: number) => void;
}

function GitHubLinks({ f }: { f: Finding }) {
  if (!f.owner || !f.repo_name) return null;
  const prUrl = `https://github.com/${f.owner}/${f.repo_name}/pull/${f.pr_number}`;
  const fileUrl = f.head_sha
    ? `https://github.com/${f.owner}/${f.repo_name}/blob/${f.head_sha}/${f.file}#L${f.line_start}`
    : null;
  return (
    <div className="flex gap-3 text-sm">
      <a href={prUrl} target="_blank" rel="noopener noreferrer"
         className="text-blue-600 underline hover:text-blue-800">
        View PR #{f.pr_number}
      </a>
      {fileUrl && (
        <a href={fileUrl} target="_blank" rel="noopener noreferrer"
           className="text-blue-600 underline hover:text-blue-800">
          View {f.file}:{f.line_start}
        </a>
      )}
    </div>
  );
}

export function FindingDrawer({ finding, onClose, onResolved }: Props) {
  if (!finding) return null;
  const isPending = finding.status === "pending";

  async function handle(action: "approve" | "dismiss") {
    try {
      const updated = action === "approve"
        ? await approveFinding(finding!.id)
        : await dismissFinding(finding!.id);
      onResolved(updated.id);
      onClose();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Action failed");
    }
  }

  return (
    <Sheet open={!!finding} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        <SheetHeader className="mb-4">
          <SheetTitle className="text-lg leading-tight">{finding.title}</SheetTitle>
          <div className="flex flex-wrap gap-2 mt-2">
            <SeverityBadge severity={finding.severity} />
            <Badge variant="outline">{finding.agent}</Badge>
            <Badge variant="secondary">{finding.category}</Badge>
            <span className="text-sm text-muted-foreground self-center">
              {(finding.specialist_conf * 100).toFixed(0)}% confidence
            </span>
          </div>
        </SheetHeader>

        <div className="space-y-5">
          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">Location</p>
            <p className="font-mono text-sm">{finding.file}:{finding.line_start}–{finding.line_end}</p>
            <GitHubLinks f={finding} />
          </div>

          <Separator />

          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">Description</p>
            <p className="text-sm leading-relaxed">{finding.description}</p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">Suggestion</p>
            <p className="text-sm leading-relaxed">{finding.suggestion}</p>
          </div>

          <Separator />

          <div>
            <p className="text-xs font-semibold uppercase text-muted-foreground mb-1">Status</p>
            <p className="text-sm capitalize">{finding.status.replace("_", " ")}</p>
            {finding.resolved_at && (
              <p className="text-xs text-muted-foreground">
                {finding.resolved_by} · {new Date(finding.resolved_at).toLocaleString()}
              </p>
            )}
          </div>

          {isPending && (
            <div className="flex gap-3 pt-2">
              <Button className="flex-1" onClick={() => handle("approve")}>
                Approve & Post to GitHub
              </Button>
              <Button variant="outline" className="flex-1" onClick={() => handle("dismiss")}>
                Dismiss
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
