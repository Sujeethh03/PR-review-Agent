import { getFindings } from "@/lib/api";
import { FindingsTable } from "@/components/FindingsTable";
import Link from "next/link";

export default async function FindingsPage() {
  const findings = await getFindings();

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
      <FindingsTable initial={findings} />
    </main>
  );
}
