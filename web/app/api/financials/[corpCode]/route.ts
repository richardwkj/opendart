import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

interface RouteParams {
  params: Promise<{ corpCode: string }>;
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { corpCode } = await params;
  const searchParams = request.nextUrl.searchParams;
  const year = searchParams.get("year");
  const reportCode = searchParams.get("report_code");
  const fsDiv = searchParams.get("fs_div");

  try {
    const company = await prisma.companies.findUnique({
      where: { corp_code: corpCode },
      select: {
        corp_code: true,
        corp_name: true,
        stock_code: true,
      },
    });

    if (!company) {
      return NextResponse.json({ error: "Company not found" }, { status: 404 });
    }

    const financialWhere: {
      corp_code: string;
      year?: number;
      report_code?: string;
      fs_div?: string;
    } = { corp_code: corpCode };

    if (year) financialWhere.year = parseInt(year, 10);
    if (reportCode) financialWhere.report_code = reportCode;
    if (fsDiv) financialWhere.fs_div = fsDiv;

    const financials = await prisma.financial_fundamentals.findMany({
      where: financialWhere,
      orderBy: [
        { year: "desc" },
        { report_code: "desc" },
        { account_name: "asc" },
      ],
      select: {
        year: true,
        report_code: true,
        fs_div: true,
        account_id: true,
        account_name: true,
        amount: true,
        version: true,
      },
    });

    const availableYears = await prisma.financial_fundamentals.findMany({
      where: { corp_code: corpCode },
      distinct: ["year"],
      orderBy: { year: "desc" },
      select: { year: true },
    });

    const availableReportCodes = await prisma.financial_fundamentals.findMany({
      where: { corp_code: corpCode, ...(year ? { year: parseInt(year, 10) } : {}) },
      distinct: ["report_code"],
      orderBy: { report_code: "desc" },
      select: { report_code: true },
    });

    return NextResponse.json({
      company,
      financials: financials.map((f) => ({
        ...f,
        amount: f.amount?.toString() ?? null,
      })),
      availableYears: availableYears.map((y) => y.year),
      availableReportCodes: availableReportCodes.map((r) => r.report_code),
    });
  } catch (error) {
    console.error("Error fetching financials:", error);
    return NextResponse.json(
      { error: "Failed to fetch financials" },
      { status: 500 }
    );
  }
}
