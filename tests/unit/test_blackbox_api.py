#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

from blackbox import BlackboxExporterApi, BlackboxExporterBadResponse


class TestBlackboxExporterApiClient(unittest.TestCase):
    def setUp(self):
        self.path = "custom/path"
        self.api = BlackboxExporterApi(f"http://address:12345/{self.path}/")

    def test_base_url(self):
        self.assertEqual(f"http://address:12345/{self.path}", self.api.base_url)

    @patch("blackbox.urllib.request.urlopen")
    def test_reload_succeed(self, urlopen_mock):
        urlopen_mock.return_value.code = 200
        urlopen_mock.return_value.reason = "OK"

        self.api.reload()
        urlopen_mock.assert_called()

    def test_reload_and_status_fail(self):
        def mock_connection_error(*args, **kwargs):
            import urllib.error

            raise urllib.error.HTTPError(
                url="mock://url",
                code=500,
                msg="mock msg",
                hdrs={"mock hdr": "mock smth"},  # type: ignore[arg-type]
                fp=None,
            )

        with patch("blackbox.urllib.request.urlopen", mock_connection_error):
            self.assertRaises(BlackboxExporterBadResponse, self.api.reload)
