import { CompanySearch } from "@/components/company-search";
import { CompanyTable } from "@/components/company-table";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="text-center py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          Korean Financial Data
        </h1>
        <p className="text-gray-600 mb-6 max-w-xl mx-auto">
          Browse financial statements and corporate disclosures for Korean listed companies.
          Data sourced from Open DART (Financial Supervisory Service).
        </p>
        <div className="flex justify-center">
          <CompanySearch />
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          All Companies
        </h2>
        <CompanyTable />
      </section>
    </div>
  );
}
