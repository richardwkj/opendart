#!/usr/bin/env python3
"""
Test script for downloading XBRL financial statement files from DART API.

API: https://opendart.fss.or.kr/api/fnlttXbrl.xml
Docs: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019019

Parameters:
- crtfc_key: API key (40 chars)
- rcept_no: Receipt number (접수번호) from disclosure search API
- reprt_code: 11013=Q1, 11012=Q2, 11014=Q3, 11011=Annual

Output: ZIP file containing XBRL documents
"""

import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://opendart.fss.or.kr/api/fnlttXbrl.xml"

DART_ERROR_CODES = {
    "000": "Success",
    "010": "Unregistered API key",
    "011": "Suspended API key",
    "012": "Blocked IP address",
    "013": "No data found",
    "014": "File does not exist",
    "020": "Request limit exceeded (20,000/day)",
    "021": "Company count limit exceeded (max 100)",
    "100": "Invalid field value",
    "101": "Unauthorized access",
    "800": "System maintenance",
    "900": "Undefined error",
    "901": "API key expired - contact opendart@fss.or.kr",
}


def download_xbrl(
    rcept_no: str,
    reprt_code: str,
    output_dir: str | Path = ".",
    api_key: str | None = None,
) -> Path | None:
    api_key = api_key or os.getenv("DART_API_KEY")
    if not api_key:
        print("Error: DART_API_KEY not set in environment")
        return None

    params = {
        "crtfc_key": api_key,
        "rcept_no": rcept_no,
        "reprt_code": reprt_code,
    }

    print(f"Downloading XBRL for rcept_no={rcept_no}, reprt_code={reprt_code}...")

    response = requests.get(API_URL, params=params, timeout=60)

    content_type = response.headers.get("Content-Type", "")
    is_error_response = "xml" in content_type or response.content.startswith(b"<?xml")

    if is_error_response:
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(response.content)
            status = root.findtext("status", "unknown")
            message = root.findtext("message", "Unknown error")
            error_desc = DART_ERROR_CODES.get(status, "Unknown status code")
            print(f"Error: [{status}] {message} ({error_desc})")
        except ET.ParseError:
            print(f"Error: Failed to parse response: {response.content[:200]}")
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"xbrl_{rcept_no}_{reprt_code}.zip"
    output_path = output_dir / filename

    with open(output_path, "wb") as f:
        f.write(response.content)

    print(f"Downloaded: {output_path} ({len(response.content):,} bytes)")

    try:
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            print(f"ZIP contents ({len(zf.namelist())} files):")
            for name in zf.namelist()[:10]:
                info = zf.getinfo(name)
                print(f"  - {name} ({info.file_size:,} bytes)")
            if len(zf.namelist()) > 10:
                print(f"  ... and {len(zf.namelist()) - 10} more files")
    except zipfile.BadZipFile:
        print("Warning: Downloaded file is not a valid ZIP")

    return output_path


def get_sample_rcept_no(corp_code: str, api_key: str | None = None) -> str | None:
    """Fetch a sample annual report receipt number for testing."""
    api_key = api_key or os.getenv("DART_API_KEY")
    if not api_key:
        return None

    list_url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": "20230101",
        "end_de": "20241231",
        "pblntf_ty": "A",
        "page_count": "10",
    }

    response = requests.get(list_url, params=params, timeout=30)
    data = response.json()

    if data.get("status") != "000":
        print(f"Error getting disclosure list: {data.get('message')}")
        return None

    for item in data.get("list", []):
        report_nm = item.get("report_nm", "")
        is_annual_report = "사업보고서" in report_nm and "첨부" not in report_nm
        if is_annual_report:
            return item.get("rcept_no")

    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Download XBRL files from DART API")
    parser.add_argument(
        "--rcept-no",
        help="Receipt number. If not provided, fetches sample for --corp-code.",
    )
    parser.add_argument(
        "--reprt-code",
        default="11011",
        choices=["11013", "11012", "11014", "11011"],
        help="Report code: 11013=Q1, 11012=Q2, 11014=Q3, 11011=Annual (default: 11011)",
    )
    parser.add_argument(
        "--corp-code",
        default="00126380",
        help="Company code for sample lookup (default: 00126380 = Samsung)",
    )
    parser.add_argument(
        "--output-dir",
        default="./xbrl_downloads",
        help="Output directory (default: ./xbrl_downloads)",
    )

    args = parser.parse_args()

    rcept_no = args.rcept_no
    if not rcept_no:
        print(f"Fetching sample receipt number for corp_code={args.corp_code}...")
        rcept_no = get_sample_rcept_no(args.corp_code)
        if not rcept_no:
            print("Error: Could not find a sample receipt number")
            print("Please provide --rcept-no manually")
            sys.exit(1)
        print(f"Found rcept_no: {rcept_no}")

    result = download_xbrl(
        rcept_no=rcept_no,
        reprt_code=args.reprt_code,
        output_dir=args.output_dir,
    )

    if result:
        print(f"\nSuccess! File saved to: {result}")
        sys.exit(0)
    else:
        print("\nFailed to download XBRL file")
        sys.exit(1)


if __name__ == "__main__":
    main()
