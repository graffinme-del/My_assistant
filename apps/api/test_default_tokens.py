"""Regression: well-known default API tokens must not work outside development."""

from __future__ import annotations

import os
import unittest
from unittest import mock


class DefaultTokenSettingsTests(unittest.TestCase):
    def test_development_allows_dev_tokens(self) -> None:
        from app.config import Settings

        with mock.patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "OWNER_TOKEN": "owner-dev-token",
                "MEMBER_TOKEN": "member-dev-token",
            },
            clear=False,
        ):
            s = Settings()
            self.assertEqual(s.owner_token, "owner-dev-token")
            self.assertEqual(s.member_token, "member-dev-token")

    def test_production_refuses_dev_tokens(self) -> None:
        from pydantic import ValidationError

        from app.config import Settings

        with mock.patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "OWNER_TOKEN": "owner-dev-token",
                "MEMBER_TOKEN": "member-dev-token",
            },
            clear=False,
        ):
            with self.assertRaises((ValidationError, ValueError)):
                Settings()

    def test_production_accepts_rotated_tokens(self) -> None:
        from app.config import Settings

        with mock.patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "OWNER_TOKEN": "prod-owner-secret-value-xyz",
                "MEMBER_TOKEN": "prod-member-secret-value-abc",
            },
            clear=False,
        ):
            s = Settings()
            self.assertEqual(s.owner_token, "prod-owner-secret-value-xyz")
            self.assertEqual(s.member_token, "prod-member-secret-value-abc")


if __name__ == "__main__":
    unittest.main()
