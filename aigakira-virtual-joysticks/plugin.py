#!/usr/bin/env python3
import json
import logging
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

PLUGIN_ID = "io.github.virtualjoysticks.plugin"
PREFIX = "io.github.virtualjoysticks."
AXIS_RANGES = {
    "x": (-32768, 32767), "y": (-32768, 32767),
    "rx": (-32768, 32767), "ry": (-32768, 32767),
    "z": (0, 255), "rz": (0, 255),
    "hat_x": (-1, 1), "hat_y": (-1, 1),
}


def action_to_command(message):
    action_id = message.get("actionId")
    data = {item["id"]: item["value"] for item in message.get("data", [])}
    if action_id == PREFIX + "button":
        base = PREFIX + "button."
        device = int(data[base + "device"])
        button = int(data[base + "number"])
        action = data[base + "action"].lower()
        if not 1 <= device <= 4 or not 1 <= button <= 32 or action not in ("pulse", "press", "release"):
            raise ValueError("invalid joystick button parameters")
        return {"type": "button", "device": device, "button": button, "action": action}
    if action_id == PREFIX + "axis":
        base = PREFIX + "axis."
        device = int(data[base + "device"])
        axis = data[base + "name"]
        value = int(data[base + "value"])
        if not 1 <= device <= 4 or axis not in AXIS_RANGES:
            raise ValueError("invalid joystick device or axis")
        minimum, maximum = AXIS_RANGES[axis]
        if not minimum <= value <= maximum:
            raise ValueError(f"{axis} must be between {minimum} and {maximum}")
        return {"type": "axis", "device": device, "axis": axis, "value": value}
    raise ValueError(f"unknown action: {action_id}")


def update_settings(settings, values):
    for item in values:
        if "UDP Host" in item:
            settings["host"] = str(item["UDP Host"]).strip() or "127.0.0.1"
        if "UDP Port" in item:
            port = int(item["UDP Port"])
            if not 1 <= port <= 65535:
                raise ValueError("UDP port must be between 1 and 65535")
            settings["port"] = port


def handle_message(message, settings, udp):
    message_type = message.get("type")
    if message_type in ("info", "settings"):
        update_settings(settings, message.get("settings" if message_type == "info" else "values", []))
        if message_type == "info":
            logging.info("Paired with Touch Portal; UDP destination %s:%s", settings["host"], settings["port"])
        else:
            logging.info("UDP destination updated to %s:%s", settings["host"], settings["port"])
    elif message_type == "action":
        command = action_to_command(message)
        udp.sendto(json.dumps(command).encode("utf-8"), (settings["host"], settings["port"]))
        logging.info("Sent %s to %s:%s", command, settings["host"], settings["port"])
    return message_type != "closePlugin"


def run_plugin():
    settings = {"host": "127.0.0.1", "port": 12100}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        while True:
            try:
                with socket.create_connection(("127.0.0.1", 12136), timeout=5) as connection:
                    connection.settimeout(None)
                    connection.sendall((json.dumps({"type": "pair", "id": PLUGIN_ID}) + "\n").encode("utf-8"))
                    logging.info("Connected to Touch Portal; waiting for pairing confirmation")
                    with connection.makefile("r", encoding="utf-8") as messages:
                        for line in messages:
                            try:
                                if not handle_message(json.loads(line), settings, udp):
                                    return
                            except (ValueError, KeyError, TypeError, OSError) as error:
                                logging.error("Could not process Touch Portal message: %s", error)
            except OSError as error:
                logging.warning("Touch Portal connection failed: %s", error)
            time.sleep(3)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if sys.platform not in ("linux", "win32"):
        logging.info("Local joystick server is only available on Linux and Windows")
        run_plugin()
        return

    server_name = "aigakira-virtual-joysticks-windows.py" if sys.platform == "win32" else "aigakira-virtual-joysticks.py"
    server_path = Path(__file__).resolve().with_name(server_name)
    if not server_path.exists():
        server_path = Path(__file__).resolve().parent.parent / server_name

    def stop_plugin(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop_plugin)
    command = [sys.executable, "-u", str(server_path)]
    if sys.platform == "win32":
        command.append("--managed")
    server = subprocess.Popen(command, stdin=subprocess.PIPE if sys.platform == "win32" else None)
    logging.info("Started local joystick server (PID %s)", server.pid)
    stopping = threading.Event()

    def monitor_server():
        exit_code = server.wait()
        if not stopping.is_set():
            logging.error("Local joystick server exited with code %s; check the preceding errors", exit_code)

    threading.Thread(target=monitor_server, daemon=True).start()
    try:
        run_plugin()
    finally:
        stopping.set()
        if server.poll() is None:
            if sys.platform == "win32":
                try:
                    server.stdin.write(b"stop\n")
                    server.stdin.flush()
                except OSError:
                    pass
            else:
                server.terminate()
            try:
                server.wait(timeout=0.4 if sys.platform == "win32" else 0.3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        if server.stdin:
            server.stdin.close()
        logging.info("Local joystick server stopped (exit code %s)", server.returncode)


if __name__ == "__main__":
    main()