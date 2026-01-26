"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface Company {
  corp_code: string;
  stock_code: string | null;
  corp_name: string;
  is_priority: boolean;
  listing_date: string | null;
  delisted_date: string | null;
}

interface Pagination {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

interface CompanyTableProps {
  initialSearch?: string;
}

export function CompanyTable({ initialSearch = "" }: CompanyTableProps) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCompanies = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: "20",
      });
      if (initialSearch) {
        params.set("search", initialSearch);
      }
      const res = await fetch(`/api/companies?${params}`);
      const data = await res.json();
      setCompanies(data.data || []);
      setPagination(data.pagination);
    } catch {
      setCompanies([]);
    } finally {
      setIsLoading(false);
    }
  }, [page, initialSearch]);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  useEffect(() => {
    setPage(1);
  }, [initialSearch]);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Company Name</TableHead>
            <TableHead>Stock Code</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {companies.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-gray-500">
                No companies found
              </TableCell>
            </TableRow>
          ) : (
            companies.map((company) => (
              <TableRow key={company.corp_code}>
                <TableCell className="font-medium">
                  {company.corp_name}
                  {company.is_priority && (
                    <Badge variant="secondary" className="ml-2">
                      Priority
                    </Badge>
                  )}
                </TableCell>
                <TableCell>{company.stock_code || "-"}</TableCell>
                <TableCell>
                  {company.delisted_date ? (
                    <Badge variant="destructive">Delisted</Badge>
                  ) : (
                    <Badge variant="default">Active</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Link href={`/companies/${company.corp_code}`}>
                    <Button variant="outline" size="sm">
                      View Financials
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {pagination && pagination.totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="flex items-center px-4 text-sm text-gray-600">
            Page {page} of {pagination.totalPages} ({pagination.total} total)
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
            disabled={page === pagination.totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
