import importlib.util
import json
import socket
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("plugin", ROOT / "aigakira-virtual-joysticks" / "plugin.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

ecodes = types.SimpleNamespace(EV_KEY=1, EV_ABS=3, ABS_X=0, ABS_Y=1, ABS_RX=3, ABS_RY=4,
                               ABS_Z=2, ABS_RZ=5, ABS_HAT0X=16, ABS_HAT0Y=17)
evdev = types.ModuleType("evdev")
evdev.UInput = object
evdev.AbsInfo = object
evdev.ecodes = ecodes
with patch.dict(sys.modules, {"evdev": evdev}):
    spec = importlib.util.spec_from_file_location("joysticks", ROOT / "aigakira-virtual-joysticks.py")
    joysticks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(joysticks)


class Device:
    def __init__(self):
        self.events = []

    def write(self, *args):
        self.events.append(args)

    def syn(self):
        pass


def action(action_name, **values):
    prefix = plugin.PREFIX + action_name
    return {"type": "action", "actionId": prefix,
            "data": [{"id": prefix + "." + key, "value": str(value)} for key, value in values.items()]}


class ProtocolTests(unittest.TestCase):
    def test_device_names(self):
        with patch.object(joysticks.e, "BTN_TRIGGER_HAPPY1", 704, create=True), \
             patch.object(joysticks.e, "BUS_USB", 3, create=True), \
             patch.object(joysticks, "AbsInfo"), \
             patch.object(joysticks, "UInput") as create_device:
            devices = joysticks.create_virtual_joysticks()
        self.assertEqual(len(devices), 4)
        self.assertEqual([call.kwargs["name"] for call in create_device.call_args_list],
                         [f"aigakira-virtual-joystick-{number}" for number in range(1, 5)])

    def test_unsupported_platform_does_not_start_server(self):
        for platform in ("darwin",):
            with self.subTest(platform=platform), \
                 patch.object(plugin.sys, "platform", platform), \
                 patch.object(plugin.subprocess, "Popen") as start, \
                 patch.object(plugin, "run_plugin") as run:
                plugin.main()
            start.assert_not_called()
            run.assert_called_once()

    def test_plugin_stops_server_on_exit(self):
        server = MagicMock(pid=1234, returncode=0)
        server.poll.return_value = None
        with (
            patch.object(plugin.sys, "platform", "linux"),
            patch.object(plugin.subprocess, "Popen", return_value=server) as start,
            patch.object(plugin.threading, "Thread") as thread,
            patch.object(plugin.signal, "signal"),
            patch.object(plugin, "run_plugin"),
        ):
            plugin.main()
        self.assertEqual(start.call_args.args[0][0:2], [sys.executable, "-u"])
        self.assertEqual(Path(start.call_args.args[0][2]).name, "aigakira-virtual-joysticks.py")
        thread.return_value.start.assert_called_once()
        server.terminate.assert_called_once()
        server.wait.assert_called_once_with(timeout=0.3)

    def test_windows_starts_and_stops_windows_server(self):
        server = MagicMock(pid=1234, returncode=0)
        server.poll.return_value = None
        with (
            patch.object(plugin.sys, "platform", "win32"),
            patch.object(plugin.subprocess, "Popen", return_value=server) as start,
            patch.object(plugin.threading, "Thread"),
            patch.object(plugin.signal, "signal"),
            patch.object(plugin, "run_plugin"),
        ):
            plugin.main()
        self.assertEqual(Path(start.call_args.args[0][2]).name, "aigakira-virtual-joysticks-windows.py")
        self.assertEqual(start.call_args.args[0][3], "--managed")
        self.assertEqual(start.call_args.kwargs["stdin"], subprocess.PIPE)
        server.stdin.write.assert_called_once_with(b"stop\n")
        server.wait.assert_called_once_with(timeout=0.4)

    def test_busy_port_does_not_create_devices(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            result = subprocess.run([sys.executable, str(ROOT / "aigakira-virtual-joysticks.py"),
                                     "--port", str(occupied.getsockname()[1])],
                                    capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error binding UDP server", result.stderr)
        self.assertNotIn("Created:", result.stdout)

    def test_udp_button_and_axis(self):
        device = Device()
        devices = [(device, list(range(32)))]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1)
            host, port = receiver.getsockname()
            settings = {"host": host, "port": port}
            for message in (action("button", device=1, number=2, action="Press"),
                            action("button", device=1, number=2, action="Release"),
                            action("axis", device=1, name="x", value=-32768)):
                plugin.handle_message(message, settings, sender)
                joysticks.handle_message(devices, json.loads(receiver.recv(4096)))
        self.assertEqual(device.events, [(1, 1, 1), (1, 1, 0), (3, 0, -32768)])

    def test_pulse_and_invalid_commands(self):
        device = Device()
        with patch.object(joysticks.time, "sleep") as sleep:
            joysticks.handle_message([(device, list(range(32)))], {"type": "button", "device": 1, "button": 1, "action": "pulse"})
        sleep.assert_called_once_with(0.2)
        self.assertEqual(device.events, [(1, 0, 1), (1, 0, 0)])
        with self.assertRaises(ValueError):
            plugin.action_to_command(action("axis", device=1, name="z", value=256))
        with self.assertRaises(ValueError):
            joysticks.handle_message([(device, list(range(32)))], {"type": "axis", "device": 1, "axis": "hat_x", "value": 2})

    def test_settings_and_manifest(self):
        settings = {"host": "127.0.0.1", "port": 12100}
        plugin.handle_message({"type": "settings", "values": [{"UDP Host": "192.0.2.1"}, {"UDP Port": "1234"}]}, settings, None)
        self.assertEqual(settings, {"host": "192.0.2.1", "port": 1234})
        manifest = json.loads((ROOT / "aigakira-virtual-joysticks" / "entry.tp").read_text())
        self.assertEqual(manifest["id"], plugin.PLUGIN_ID)
        self.assertEqual(manifest["version"], 1)
        self.assertEqual((ROOT / "VERSION").read_text().strip(), "0.0.1")
        self.assertIn("plugin_start_cmd_linux", manifest)
        self.assertNotIn("plugin_start_cmd", manifest)
        self.assertEqual(manifest["plugin_start_cmd_windows"], "py -3 plugin.py")
        self.assertNotIn("plugin_start_cmd_mac", manifest)
        self.assertEqual({item["id"] for item in manifest["categories"][0]["actions"]}, {plugin.PREFIX + "button", plugin.PREFIX + "axis"})


if __name__ == "__main__":
    unittest.main()