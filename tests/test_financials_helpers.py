from datetime import datetime

import pandas as pd

from opendart.etl.financials import parse_amount, transform_financial_data


def test_parse_amount():
    assert parse_amount("1,234") == 1234
    assert parse_amount("-") is None
    assert parse_amount(None) is None
    assert parse_amount(1000) == 1000
    assert parse_amount("bad") is None


def test_transform_financial_data():
    df = pd.DataFrame(
        [
            {
                "fs_div": "CFS",
                "account_id": "ifrs_Full_Revenue",
                "account_nm": "Revenue",
                "thstrm_amount": "1,000",
            }
        ]
    )

    records = transform_financial_data(df, "00000123", 2023, "11011")

    assert len(records) == 1
    record = records[0]
    assert record["corp_code"] == "00000123"
    assert record["year"] == 2023
    assert record["report_code"] == "11011"
    assert record["fs_div"] == "CFS"
    assert record["account_id"] == "ifrs_Full_Revenue"
    assert record["account_name"] == "Revenue"
    assert record["amount"] == 1000
    assert record["version"] == 1
    assert isinstance(record["fetched_at"], datetime)


def test_transform_financial_data_empty():
    records = transform_financial_data(pd.DataFrame(), "00000123", 2023, "11011")
    assert records == []
