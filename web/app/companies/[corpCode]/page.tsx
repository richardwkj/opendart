import Link from "next/link";
import { FinancialTable } from "@/components/financial-table";
import { Button } from "@/components/ui/button";

interface PageProps {
  params: Promise<{ corpCode: string }>;
}

export default async function CompanyPage({ params }: PageProps) {
  const { corpCode } = await params;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/">
          <Button variant="outline" size="sm">
            ← Back to Companies
          </Button>
        </Link>
      </div>

      <FinancialTable corpCode={corpCode} />
    </div>
  );
}
