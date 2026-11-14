#!/usr/bin/env python3
import argparse
import json
import math
import socket
import sys
import threading
import time

AXES = {
    "x": (0x30, -32768, 32767),
    "y": (0x31, -32768, 32767),
    "z": (0x32, 0, 255),
    "rx": (0x33, -32768, 32767),
    "ry": (0x34, -32768, 32767),
    "rz": (0x35, 0, 255),
}
PULSE_DURATION = 0.2


class VJoyReceiver:
    def __init__(self, devices):
        self.devices = devices
        self.hats = [{"hat_x": 0, "hat_y": 0} for device in devices]

    def handle_message(self, message):
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        device_number = message.get("device")
        if type(device_number) is not int or not 1 <= device_number <= len(self.devices):
            raise ValueError("device must be an available device number")
        device = self.devices[device_number - 1]
        if message.get("type") == "button":
            button = message.get("button")
            action = message.get("action")
            if type(button) is not int or not 1 <= button <= 32:
                raise ValueError("button must be between 1 and 32")
            if action not in ("pulse", "press", "release"):
                raise ValueError("button action must be pulse, press or release")
            device.set_button(button, int(action != "release"))
            if action == "pulse":
                try:
                    time.sleep(PULSE_DURATION)
                finally:
                    device.set_button(button, 0)
        elif message.get("type") == "axis":
            axis = message.get("axis")
            value = message.get("value")
            if not isinstance(axis, str) or (axis not in AXES and axis not in ("hat_x", "hat_y")):
                raise ValueError("unknown axis")
            if axis in ("hat_x", "hat_y"):
                if type(value) is not int or not -1 <= value <= 1:
                    raise ValueError("hat value must be between -1 and 1")
                hat = self.hats[device_number - 1].copy()
                hat[axis] = value
                x, y = hat["hat_x"], hat["hat_y"]
                angle = round(math.degrees(math.atan2(x, -y)) * 100) % 36000 if x or y else -1
                if not device.set_cont_pov(1, angle):
                    raise RuntimeError("could not set vJoy continuous POV 1")
                self.hats[device_number - 1] = hat
            else:
                axis_code, minimum, maximum = AXES[axis]
                if type(value) is not int or not minimum <= value <= maximum:
                    raise ValueError(f"axis value must be between {minimum} and {maximum}")
                scaled = ((value - minimum) * 32767 + (maximum - minimum) // 2) // (maximum - minimum)
                device.set_axis(axis_code, scaled)
        else:
            raise ValueError("unknown message type")


def main():
    parser = argparse.ArgumentParser(description="Receive UDP commands for Windows vJoy devices")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=12100)
    parser.add_argument("--managed", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        import pyvjoy
    except (ImportError, OSError) as error:
        sys.exit(f"Cannot load pyvjoy: {error}. Install Python, pyvjoy and the vJoy driver.")

    devices = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        try:
            server.bind((args.host, args.port))
            for number in range(1, 5):
                devices.append(pyvjoy.VJoyDevice(number))
                print(f"Acquired vJoy device {number}", flush=True)
            receiver = VJoyReceiver(devices)
            stopping = threading.Event()
            if args.managed:
                def wait_for_parent():
                    sys.stdin.buffer.readline()
                    stopping.set()
                threading.Thread(target=wait_for_parent, daemon=True).start()
                server.settimeout(0.1)
            host, port = server.getsockname()
            print(f"Listening for joystick commands on {host}:{port}", flush=True)
            while not stopping.is_set():
                try:
                    data, address = server.recvfrom(4096)
                except socket.timeout:
                    continue
                try:
                    message = json.loads(data)
                    receiver.handle_message(message)
                    print(f"Command from {address[0]}:{address[1]}: {message}", flush=True)
                except (ValueError, UnicodeDecodeError, RuntimeError, NameError, pyvjoy.vJoyException) as error:
                    print(f"Invalid or failed command from {address}: {error}", file=sys.stderr, flush=True)
        except KeyboardInterrupt:
            print("Shutting down vJoy devices", flush=True)
        except (OSError, pyvjoy.vJoyException) as error:
            print(f"Could not start vJoy server: {error}", file=sys.stderr, flush=True)
            return 1
        finally:
            for device in devices:
                try:
                    device.reset()
                except Exception as error:
                    print(f"Could not reset vJoy device: {error}", file=sys.stderr, flush=True)
            devices.clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())