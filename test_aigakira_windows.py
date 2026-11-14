import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location("windows_server", Path(__file__).parent / "aigakira-virtual-joysticks-windows.py")
windows_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(windows_server)


class WindowsServerTests(unittest.TestCase):
    def setUp(self):
        self.device = MagicMock()
        self.device.set_cont_pov.return_value = True
        self.receiver = windows_server.VJoyReceiver([self.device])

    def test_button_pulse_and_release(self):
        with patch.object(windows_server.time, "sleep") as sleep:
            self.receiver.handle_message({"type": "button", "device": 1, "button": 32, "action": "pulse"})
        self.assertEqual(self.device.set_button.call_args_list, [unittest.mock.call(32, 1), unittest.mock.call(32, 0)])
        sleep.assert_called_once_with(0.2)

    def test_axis_ranges_and_hat_diagonals(self):
        for axis, value in (("x", -32768), ("x", 0), ("x", 32767), ("z", 255)):
            self.receiver.handle_message({"type": "axis", "device": 1, "axis": axis, "value": value})
        self.assertEqual(self.device.set_axis.call_args_list, [unittest.mock.call(0x30, 0), unittest.mock.call(0x30, 16384), unittest.mock.call(0x30, 32767), unittest.mock.call(0x32, 32767)])
        for axis, value in (("hat_y", -1), ("hat_x", 1), ("hat_y", 0), ("hat_x", 0)):
            self.receiver.handle_message({"type": "axis", "device": 1, "axis": axis, "value": value})
        self.assertEqual(self.device.set_cont_pov.call_args_list, [unittest.mock.call(1, 0), unittest.mock.call(1, 4500), unittest.mock.call(1, 9000), unittest.mock.call(1, -1)])

    def test_invalid_input_rejected(self):
        for message in ({"type": "button", "device": 1, "button": 33, "action": "press"},
                        {"type": "axis", "device": 1, "axis": "z", "value": 256},
                        {"type": "axis", "device": True, "axis": "x", "value": 0}):
            with self.assertRaises(ValueError):
                self.receiver.handle_message(message)

    def test_server_receives_datagram_and_resets_devices(self):
        devices = [MagicMock() for number in range(4)]
        fake_vjoy = types.SimpleNamespace(VJoyDevice=MagicMock(side_effect=devices), vJoyException=RuntimeError)
        server = MagicMock()
        server.getsockname.return_value = ("127.0.0.1", 12100)
        message = {"type": "button", "device": 1, "button": 2, "action": "press"}
        server.recvfrom.side_effect = [(json.dumps(message).encode(), ("127.0.0.1", 1234)), KeyboardInterrupt()]
        server_context = MagicMock()
        server_context.__enter__.return_value = server
        with (
            patch.dict(sys.modules, {"pyvjoy": fake_vjoy}),
            patch.object(sys, "argv", ["server"]),
            patch.object(windows_server.socket, "socket", return_value=server_context),
        ):
            self.assertEqual(windows_server.main(), 0)
        server.bind.assert_called_once_with(("127.0.0.1", 12100))
        devices[0].set_button.assert_called_once_with(2, 1)
        for device in devices:
            device.reset.assert_called_once()


if __name__ == "__main__":
    unittest.main()