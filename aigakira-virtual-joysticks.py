#!/usr/bin/env python3
"""
Virtual Joystick Generator for Linux (uinput / evdev)
Creates 4 virtual joystick devices with 32 buttons each (128 buttons total)
plus full analog axes and hats for complete Steam, Proton, and SDL2 recognition.
"""
import argparse
import json
import socket
import time
import sys
from evdev import UInput, AbsInfo, ecodes as e

NUM_DEVICES = 4
BUTTONS_PER_DEVICE = 32
PULSE_DURATION = 0.2

def create_virtual_joysticks():
    # 32 buttons per device using BTN_TRIGGER_HAPPY codes
    buttons = [e.BTN_TRIGGER_HAPPY1 + i for i in range(BUTTONS_PER_DEVICE)]
    
    # Full suite of axes required for Steam / Proton / SDL2 gamepad detection
    axes = [
        (e.ABS_X, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),      # Left Stick X
        (e.ABS_Y, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),      # Left Stick Y
        (e.ABS_RX, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),     # Right Stick X
        (e.ABS_RY, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),     # Right Stick Y
        (e.ABS_Z, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),            # Left Trigger
        (e.ABS_RZ, AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),           # Right Trigger
        (e.ABS_THROTTLE, AbsInfo(value=0, min=-32768, max=32767, fuzz=0, flat=0, resolution=0)),
        (e.ABS_HAT0X, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),          # D-Pad Hat X
        (e.ABS_HAT0Y, AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),          # D-Pad Hat Y
    ]
    
    capabilities = {
        e.EV_KEY: buttons,
        e.EV_ABS: axes
    }

    devices = []
    for i in range(NUM_DEVICES):
        dev_name = f"aigakira-virtual-joystick-{i + 1}"
        try:
            ui = UInput(
                capabilities,
                name=dev_name,
                bustype=e.BUS_USB,
                vendor=0x1234,
                product=0x5670 + (i + 1),
                version=0x1
            )
            devices.append((ui, buttons))
            print(f"[+] Created: {dev_name} ({BUTTONS_PER_DEVICE} buttons + full analog/hat axes)")
        except Exception as ex:
            print(f"[-] Failed to create {dev_name}: {ex}", file=sys.stderr)
            for created, _ in devices:
                created.close()
            return []

    return devices

def trigger_button(devices, device_index, button_index):
    """Trigger a button press and release on a specific device and button index."""
    if 0 <= device_index < len(devices):
        ui, buttons = devices[device_index]
        if 0 <= button_index < len(buttons):
            btn_code = buttons[button_index]
            ui.write(e.EV_KEY, btn_code, 1)  # Press
            ui.syn()
            time.sleep(PULSE_DURATION)
            ui.write(e.EV_KEY, btn_code, 0)  # Release
            ui.syn()

def set_axis(devices, device_index, axis_code, value):
    """Set an analog or hat axis value on a specific device."""
    if 0 <= device_index < len(devices):
        ui, _ = devices[device_index]
        ui.write(e.EV_ABS, axis_code, value)
        ui.syn()

AXES = {
    "x": (e.ABS_X, -32768, 32767),
    "y": (e.ABS_Y, -32768, 32767),
    "rx": (e.ABS_RX, -32768, 32767),
    "ry": (e.ABS_RY, -32768, 32767),
    "z": (e.ABS_Z, 0, 255),
    "rz": (e.ABS_RZ, 0, 255),
    "hat_x": (e.ABS_HAT0X, -1, 1),
    "hat_y": (e.ABS_HAT0Y, -1, 1),
}

def handle_message(devices, message):
    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    device = message.get("device")
    if type(device) is not int or not 1 <= device <= len(devices):
        raise ValueError("device must be an available device number")
    device_index = device - 1
    if message.get("type") == "button":
        button = message.get("button")
        if type(button) is not int or not 1 <= button <= BUTTONS_PER_DEVICE:
            raise ValueError("button must be between 1 and 32")
        action = message.get("action")
        if action == "pulse":
            trigger_button(devices, device_index, button - 1)
        elif action in ("press", "release"):
            ui, buttons = devices[device_index]
            ui.write(e.EV_KEY, buttons[button - 1], int(action == "press"))
            ui.syn()
        else:
            raise ValueError("button action must be pulse, press or release")
    elif message.get("type") == "axis":
        axis = message.get("axis")
        if not isinstance(axis, str) or axis not in AXES:
            raise ValueError("unknown axis")
        axis_code, minimum, maximum = AXES[axis]
        value = message.get("value")
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"axis value must be between {minimum} and {maximum}")
        set_axis(devices, device_index, axis_code, value)
    else:
        raise ValueError("unknown message type")

def serve(devices, host, port, server=None):
    with server if server is not None else socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        if server.getsockname()[1] == 0:
            server.bind((host, port))
        bound_host, bound_port = server.getsockname()
        print(f"Listening for joystick commands on {bound_host}:{bound_port}", flush=True)
        while True:
            data, address = server.recvfrom(4096)
            try:
                message = json.loads(data)
                handle_message(devices, message)
                print(f"Command from {address[0]}:{address[1]}: {message}", flush=True)
            except (ValueError, UnicodeDecodeError) as error:
                print(f"Invalid command from {address}: {error}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create virtual joysticks and receive UDP commands")
    parser.add_argument("--host", default="127.0.0.1", help="UDP bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=12100, help="UDP port (default: 12100)")
    args = parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        try:
            server.bind((args.host, args.port))
        except OSError as error:
            print(f"Error binding UDP server to {args.host}:{args.port}: {error}", file=sys.stderr)
            sys.exit(1)

        print("Initializing 4 virtual joysticks with full axes for Steam/Proton...")
        devices = create_virtual_joysticks()
        if not devices:
            print("Error: Could not create all devices. Check /dev/uinput permissions.", file=sys.stderr)
            sys.exit(1)

        try:
            serve(devices, args.host, args.port, server)
        except KeyboardInterrupt:
            print("\nShutting down virtual devices...")
        finally:
            for ui, _ in devices:
                ui.close()
