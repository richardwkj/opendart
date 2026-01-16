# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Korean Financial Data Automator - an ETL system that pulls financial fundamentals and corporate events for Korean listed companies from the Open DART API and stores them in a relational database.

## Tech Stack

- Python 3.10+
- OpenDartReader library (wraps Open DART API)
- PostgreSQL (recommended), MySQL, or SQLite
- APScheduler for internal scheduling

## Key Domain Concepts

- **corp_code**: DART's 8-digit company identifier (stable, used as PK) - more reliable than stock_code which can be reused after delisting
- **stock_code**: 6-digit KRX ticker (may be reused)
- **report_code**: Quarterly identifier - `11013` (Q1), `11012` (Q2), `11014` (Q3), `11011` (Q4/Annual)
- **fs_div**: Financial statement division - `CFS` (consolidated) or `OFS` (standalone)

## Database Schema

Three main tables with `corp_code` as the linking key:
- `Companies` (master) - company identifiers, listing/delisting dates, priority flag
- `Financial_Fundamentals` (detail) - financial statement line items with versioning for restatements
- `Key_Events` (detail) - disclosures keyed by `rcept_no`

View: `Latest_Financials` - shows only the most recent version of each financial entry.

## API Constraints

- **Daily limit**: 20,000 requests
- **Throttling**: 0.15s delay between requests
- **Data availability**: `finstate_all()` available from 2015 Q1 onwards
- **Error codes**: 010 (unregistered key), 011 (expired), 013 (no data), 020 (rate limit), 800 (data doesn't exist)

## Configuration

API keys and database credentials stored in `.env` file (gitignored).
