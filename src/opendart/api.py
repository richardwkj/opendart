"""OpenDartReader API client with rate limiting and error handling."""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import OpenDartReader
import pandas as pd

from opendart.config import get_settings

logger = logging.getLogger(__name__)


class DartErrorCode(Enum):
    """DART API error codes."""

    UNREGISTERED_KEY = "010"
    EXPIRED_KEY = "011"
    NO_DATA = "013"
    RATE_LIMIT = "020"
    DATA_NOT_EXIST = "800"


@dataclass
class DartError(Exception):
    """Exception for DART API errors."""

    code: str
    message: str

    def __str__(self) -> str:
        return f"DART Error {self.code}: {self.message}"


class DartClient:
    """Wrapper around OpenDartReader with rate limiting and error handling."""

    def __init__(self, api_key: str | None = None):
        """Initialize the DART client.

        Args:
            api_key: DART API key. If not provided, reads from environment.
        """
        settings = get_settings()
        self.api_key = api_key or settings.dart_api_key
        self.request_delay = settings.request_delay
        self.rate_limit_pause = settings.rate_limit_pause

        self._dart = OpenDartReader(self.api_key)
        self._last_request_time: float = 0

    def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            sleep_time = self.request_delay - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _check_error(self, result: Any, context: str = "") -> None:
        """Check API result for errors.

        Args:
            result: API response (DataFrame or dict)
            context: Description of the operation for logging
        """
        # Check if result is a dict with error status
        if isinstance(result, dict):
            status = result.get("status")
            if status and status != "000":
                message = result.get("message", "Unknown error")
                logger.error(f"DART API error in {context}: {status} - {message}")
                raise DartError(code=status, message=message)

        # Check if result is a DataFrame that indicates an error
        if isinstance(result, pd.DataFrame):
            if result.empty:
                # Empty result is not necessarily an error
                return
            # Check for status column in some responses
            if "status" in result.columns:
                status = result["status"].iloc[0]
                if status and str(status) != "000":
                    message = result.get("message", ["Unknown"])[0]
                    logger.error(f"DART API error in {context}: {status} - {message}")
                    raise DartError(code=str(status), message=str(message))

    def finstate_all(
        self,
        corp_code: str,
        bsns_year: int,
        reprt_code: str,
    ) -> pd.DataFrame:
        """Fetch all financial statement data for a company.

        Args:
            corp_code: DART company code
            bsns_year: Business year (e.g., 2024)
            reprt_code: Report code (11011=annual, 11013=Q1, 11012=Q2, 11014=Q3)

        Returns:
            DataFrame with financial statement data

        Raises:
            DartError: If API returns an error
        """
        self._wait_for_rate_limit()
        context = f"finstate_all({corp_code}, {bsns_year}, {reprt_code})"

        try:
            logger.debug(f"Calling {context}")
            result = self._dart.finstate_all(
                corp=corp_code,
                bsns_year=bsns_year,
                reprt_code=reprt_code,
            )

            if result is None:
                logger.warning(f"No data returned for {context}")
                return pd.DataFrame()

            self._check_error(result, context)
            return result

        except DartError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {context}: {e}")
            raise

    def list(
        self,
        corp_code: str | None = None,
        start: str | None = None,
        end: str | None = None,
        kind: str | None = None,
        kind_detail: str | None = None,
    ) -> pd.DataFrame:
        """Fetch disclosure list.

        Args:
            corp_code: DART company code (optional)
            start: Start date YYYYMMDD
            end: End date YYYYMMDD
            kind: Disclosure type (A=report, B=major issues, C=acquisition, etc.)
            kind_detail: Detail type

        Returns:
            DataFrame with disclosure list
        """
        self._wait_for_rate_limit()
        context = f"list({corp_code}, {start}-{end}, kind={kind})"

        try:
            logger.debug(f"Calling {context}")
            result = self._dart.list(
                corp=corp_code,
                start=start,
                end=end,
                kind=kind,
                kind_detail=kind_detail,
            )

            if result is None:
                return pd.DataFrame()

            self._check_error(result, context)
            return result

        except DartError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {context}: {e}")
            raise

    def company(self, corp_code: str) -> dict[str, Any]:
        """Fetch company information.

        Args:
            corp_code: DART company code

        Returns:
            Dictionary with company info
        """
        self._wait_for_rate_limit()
        context = f"company({corp_code})"

        try:
            logger.debug(f"Calling {context}")
            result = self._dart.company(corp_code)

            if result is None:
                return {}

            self._check_error(result, context)
            return result

        except DartError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {context}: {e}")
            raise

    def corp_codes(self) -> pd.DataFrame:
        """Fetch all company codes.

        Returns:
            DataFrame with all company codes
        """
        self._wait_for_rate_limit()
        context = "corp_codes()"

        try:
            logger.debug(f"Calling {context}")
            result = self._dart.corp_codes

            if result is None:
                return pd.DataFrame()

            return result

        except Exception as e:
            logger.error(f"Unexpected error in {context}: {e}")
            raise


def get_dart_client() -> DartClient:
    """Get a configured DART client instance."""
    return DartClient()
