"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatKRW, formatReportPeriod, FS_DIV_LABELS } from "@/lib/format";

interface Financial {
  year: number;
  report_code: string;
  fs_div: string;
  account_id: string;
  account_name: string;
  amount: string | null;
  version: number;
}

interface Company {
  corp_code: string;
  corp_name: string;
  stock_code: string | null;
}

interface FinancialTableProps {
  corpCode: string;
}

export function FinancialTable({ corpCode }: FinancialTableProps) {
  const [company, setCompany] = useState<Company | null>(null);
  const [financials, setFinancials] = useState<Financial[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [availableReportCodes, setAvailableReportCodes] = useState<string[]>([]);
  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedReportCode, setSelectedReportCode] = useState<string>("");
  const [selectedFsDiv, setSelectedFsDiv] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  const fetchFinancials = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedYear) params.set("year", selectedYear);
      if (selectedReportCode) params.set("report_code", selectedReportCode);
      if (selectedFsDiv) params.set("fs_div", selectedFsDiv);

      const res = await fetch(`/api/financials/${corpCode}?${params}`);
      const data = await res.json();

      setCompany(data.company);
      setFinancials(data.financials || []);
      setAvailableYears(data.availableYears || []);
      setAvailableReportCodes(data.availableReportCodes || []);

      if (!selectedYear && data.availableYears?.length > 0) {
        setSelectedYear(data.availableYears[0].toString());
      }
    } catch {
      setFinancials([]);
    } finally {
      setIsLoading(false);
    }
  }, [corpCode, selectedYear, selectedReportCode, selectedFsDiv]);

  useEffect(() => {
    fetchFinancials();
  }, [fetchFinancials]);

  const filteredFinancials = financials.filter((f) => {
    if (selectedFsDiv && f.fs_div !== selectedFsDiv) return false;
    return true;
  });

  const uniqueFsDivs = [...new Set(financials.map((f) => f.fs_div))];

  if (isLoading && !company) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="flex gap-4">
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-32" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {company && (
        <div>
          <h1 className="text-2xl font-bold">{company.corp_name}</h1>
          {company.stock_code && (
            <p className="text-gray-500">Stock Code: {company.stock_code}</p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-4">
        <Select value={selectedYear} onValueChange={setSelectedYear}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            {availableYears.map((year) => (
              <SelectItem key={year} value={year.toString()}>
                {year}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={selectedReportCode}
          onValueChange={setSelectedReportCode}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Period" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All Periods</SelectItem>
            {availableReportCodes.map((code) => (
              <SelectItem key={code} value={code}>
                {selectedYear
                  ? formatReportPeriod(parseInt(selectedYear), code)
                  : code}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={selectedFsDiv} onValueChange={setSelectedFsDiv}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Statement Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All Types</SelectItem>
            {uniqueFsDivs.map((div) => (
              <SelectItem key={div} value={div}>
                {FS_DIV_LABELS[div] || div}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Period Ending</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Account</TableHead>
              <TableHead className="text-right">Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredFinancials.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-gray-500">
                  No financial data available
                </TableCell>
              </TableRow>
            ) : (
              filteredFinancials.map((f, idx) => (
                <TableRow key={`${f.account_id}-${f.year}-${f.report_code}-${idx}`}>
                  <TableCell>
                    {formatReportPeriod(f.year, f.report_code)}
                  </TableCell>
                  <TableCell>{FS_DIV_LABELS[f.fs_div] || f.fs_div}</TableCell>
                  <TableCell>{f.account_name}</TableCell>
                  <TableCell className="text-right font-mono">
                    {formatKRW(f.amount)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
