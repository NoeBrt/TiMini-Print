from __future__ import annotations

import subprocess
import unittest
from unittest.mock import Mock, patch

from timiniprint.transport.bluetooth.adapters.linux_cmd import LinuxCommandTools


class LinuxCmdTests(unittest.TestCase):
    def test_scan_devices_parses_devices_and_paired(self) -> None:
        tools = LinuxCommandTools()

        def run_bt(args, timeout=None):
            _ = timeout
            cmd = tuple(args)
            if cmd == ("--timeout", "5", "scan", "on"):
                return ""
            if cmd == ("devices",):
                return "Device AA:BB:CC:DD:EE:01 X6H\nDevice AA:BB:CC:DD:EE:02 M50 \n"
            if cmd == ("devices", "Paired"):
                return "Device AA:BB:CC:DD:EE:01 X6H\n"
            return ""

        with patch.object(tools, "_has_bluetoothctl", return_value=True), patch.object(
            tools, "_run_bluetoothctl", side_effect=run_bt
        ):
            devices, paired = tools.scan_devices(5.0)
        self.assertEqual(len(devices), 2)
        self.assertIn("AA:BB:CC:DD:EE:01", paired)
        self.assertTrue(devices[0].paired or devices[1].paired)
        self.assertIn("M50 ", {device.name for device in devices})

    def test_resolve_rfcomm_channels_parsing(self) -> None:
        output = """
Service Name: Serial Port
Channel: 7

Service Name: Other
Channel: 3
"""
        with patch("shutil.which", return_value="/usr/bin/sdptool"), patch(
            "subprocess.run", return_value=Mock(stdout=output)
        ):
            channels = LinuxCommandTools().resolve_rfcomm_channels("AA:BB")
        self.assertEqual(channels, [7])

        output2 = "Service Name: Other\nChannel: 2\n"
        with patch("shutil.which", return_value="/usr/bin/sdptool"), patch(
            "subprocess.run", return_value=Mock(stdout=output2)
        ):
            channels2 = LinuxCommandTools().resolve_rfcomm_channels("AA:BB")
        self.assertEqual(channels2, [2])

        with patch("shutil.which", return_value="/usr/bin/sdptool"), patch(
            "subprocess.run", side_effect=subprocess.SubprocessError("x")
        ):
            self.assertEqual(LinuxCommandTools().resolve_rfcomm_channels("AA"), [])

    def test_resolve_rfcomm_channels_falls_back_to_serial_port_search(self) -> None:
        # Printers whose SDP records sit outside the public browse group are invisible to `browse`.
        search_output = "Service Name: JL_SPP\nChannel: 2\n"

        def run(command, **_kwargs):
            return Mock(stdout=search_output if command[1] == "search" else "")

        with patch("shutil.which", return_value="/usr/bin/sdptool"), patch(
            "subprocess.run", side_effect=run
        ) as runner:
            channels = LinuxCommandTools().resolve_rfcomm_channels("AA:BB")
        self.assertEqual(channels, [2])
        self.assertEqual(
            runner.call_args.args[0], ["sdptool", "search", "--bdaddr", "AA:BB", "SP"]
        )

    def test_ensure_paired_flow(self) -> None:
        tools = LinuxCommandTools()
        with patch.object(tools, "_has_bluetoothctl", return_value=True), patch.object(
            tools, "_bluetoothctl_is_paired", side_effect=[False, True]
        ), patch.object(tools, "_bluetoothctl_pair") as pair_mock, patch.object(tools, "_bluetoothctl_trust") as trust_mock:
            tools.ensure_paired("AA")
        self.assertEqual(pair_mock.call_count, 1)
        self.assertEqual(trust_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
