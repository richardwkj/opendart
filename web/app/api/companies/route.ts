import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const search = searchParams.get("search") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = parseInt(searchParams.get("limit") || "20", 10);
  const priorityOnly = searchParams.get("priority") === "true";

  const skip = (page - 1) * limit;

  const where: {
    is_priority?: boolean;
    OR?: Array<{
      corp_name?: { contains: string; mode: "insensitive" };
      stock_code?: { contains: string; mode: "insensitive" };
    }>;
  } = {};

  if (priorityOnly) {
    where.is_priority = true;
  }

  if (search) {
    where.OR = [
      { corp_name: { contains: search, mode: "insensitive" } },
      { stock_code: { contains: search, mode: "insensitive" } },
    ];
  }

  try {
    const [companies, total] = await Promise.all([
      prisma.companies.findMany({
        where,
        skip,
        take: limit,
        orderBy: [{ is_priority: "desc" }, { corp_name: "asc" }],
        select: {
          corp_code: true,
          stock_code: true,
          corp_name: true,
          is_priority: true,
          listing_date: true,
          delisted_date: true,
        },
      }),
      prisma.companies.count({ where }),
    ]);

    return NextResponse.json({
      data: companies,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });
  } catch (error) {
    console.error("Error fetching companies:", error);
    return NextResponse.json(
      { error: "Failed to fetch companies" },
      { status: 500 }
    );
  }
}
