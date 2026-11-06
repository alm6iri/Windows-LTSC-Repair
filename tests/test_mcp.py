"""Regression tests for MCP integration using the real WindowsInfo type."""

# Copyright (c) 2026 alm6iri. All rights reserved.
# Use is governed by the Personal and Internal Use License in LICENSE.

import json
import unittest
from unittest import mock

import mcp_server
from repair_core.platform_info import WindowsInfo


class TestMCPIntegration(unittest.TestCase):
    def test_detection_is_json_serializable(self):
        info = WindowsInfo()
        with mock.patch.object(mcp_server.platform_info, "detect", return_value=info):
            result = mcp_server._detect_platform()
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["details"]["is_windows"])
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_repair_receives_real_info_and_emits_events(self):
        info = WindowsInfo()
        info.available = True
        module = mock.Mock()
        with (
            mock.patch.object(mcp_server.platform_info, "detect", return_value=info),
            mock.patch.object(mcp_server, "_is_admin", return_value=True),
        ):
            result = mcp_server._run_repair_tool(
                "run_network_repair", module, "net_start", "net_end"
            )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["events"]), 2)
        module.repair.assert_called_once()
        self.assertIs(module.repair.call_args.args[1], info)
        self.assertFalse(mcp_server._LOCK.locked())

    def test_non_windows_repair_blocks_without_mutation(self):
        module = mock.Mock()
        with mock.patch.object(
            mcp_server.platform_info, "detect", return_value=WindowsInfo()
        ):
            result = mcp_server._run_repair_tool(
                "run_network_repair", module, "net_start", "net_end"
            )
        self.assertEqual(result["status"], "blocked")
        module.repair.assert_not_called()
        self.assertFalse(mcp_server._LOCK.locked())

    def test_non_admin_repair_blocks_without_mutation(self):
        info = WindowsInfo()
        info.available = True
        module = mock.Mock()
        with (
            mock.patch.object(mcp_server.platform_info, "detect", return_value=info),
            mock.patch.object(mcp_server, "_is_admin", return_value=False),
        ):
            result = mcp_server._run_repair_tool(
                "run_network_repair", module, "net_start", "net_end"
            )
        self.assertEqual(result["status"], "blocked")
        module.repair.assert_not_called()

    def test_non_windows_reboot_blocks_without_shutdown(self):
        with (
            mock.patch.object(
                mcp_server.platform_info, "detect", return_value=WindowsInfo()
            ),
            mock.patch("subprocess.run") as shutdown,
        ):
            result = mcp_server._reboot_system(True)
        self.assertEqual(result["status"], "blocked")
        shutdown.assert_not_called()
