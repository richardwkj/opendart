# OpenDART Web Dashboard

Web interface for browsing Korean financial data collected by the OpenDART ETL system.

## Features

- **Company Search**: Search companies by name or stock code
- **Company List**: Browse all tracked companies with pagination
- **Financial Statements**: View financial line items by year and quarter
  - Filter by period (date ending format: 2024-03-31, 2024-06-30, etc.)
  - Filter by statement type (Consolidated/Standalone)

## Tech Stack

- Next.js 16 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Prisma ORM

## Local Development

```bash
# Install dependencies
npm install

# Set up environment
cp .env.example .env
# Edit .env with your PostgreSQL connection string

# Generate Prisma client
npx prisma generate

# Start dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Database Connection

This app connects to the same PostgreSQL database used by the OpenDART ETL system. The database must have the following tables:
- `companies` - Company master data
- `financial_fundamentals` - Financial statement line items
- `key_events` - Corporate disclosure events

## Vercel Deployment

1. Push code to GitHub
2. Import project in Vercel
3. Configure environment variable:
   - `DATABASE_URL`: PostgreSQL connection string with SSL
     ```
     postgresql://user:password@host:5432/opendart_updater?sslmode=require
     ```
4. Deploy

### Database Considerations for Production

For Vercel deployment, you'll need a cloud-accessible PostgreSQL database:
- **Neon** (recommended): Serverless Postgres with generous free tier
- **Supabase**: Postgres with additional features
- **Railway**: Simple managed Postgres
- **Vercel Postgres**: Native Vercel integration

If using your existing database, ensure:
1. Database is accessible from internet (not just localhost)
2. SSL is enabled (`?sslmode=require`)
3. Connection pooling is configured (Prisma Accelerate or PgBouncer)
