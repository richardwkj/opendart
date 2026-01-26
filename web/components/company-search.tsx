"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";

interface Company {
  corp_code: string;
  stock_code: string | null;
  corp_name: string;
}

export function CompanySearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Company[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const search = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch(
        `/api/companies?search=${encodeURIComponent(searchQuery)}&limit=10`
      );
      const data = await res.json();
      setResults(data.data || []);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      search(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, search]);

  const handleSelect = (corpCode: string) => {
    setIsOpen(false);
    setQuery("");
    router.push(`/companies/${corpCode}`);
  };

  return (
    <div className="relative w-full max-w-md">
      <Input
        type="text"
        placeholder="Search company name or stock code..."
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 200)}
        className="w-full"
      />
      {isOpen && (query.trim() || isLoading) && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto">
          {isLoading ? (
            <div className="p-3 text-gray-500 text-sm">Searching...</div>
          ) : results.length > 0 ? (
            results.map((company) => (
              <button
                key={company.corp_code}
                className="w-full px-4 py-2 text-left hover:bg-gray-100 flex justify-between items-center"
                onMouseDown={() => handleSelect(company.corp_code)}
              >
                <span className="font-medium">{company.corp_name}</span>
                {company.stock_code && (
                  <span className="text-gray-500 text-sm">
                    {company.stock_code}
                  </span>
                )}
              </button>
            ))
          ) : query.trim() ? (
            <div className="p-3 text-gray-500 text-sm">No results found</div>
          ) : null}
        </div>
      )}
    </div>
  );
}
