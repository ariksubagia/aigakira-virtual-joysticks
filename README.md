# Aigakira Virtual Joysticks

Current version: **0.0.1**

A Touch Portal plugin that turns button and axis actions into virtual joystick input. It starts a local UDP server automatically when the plugin runs: Linux uses `uinput`, while Windows uses the vJoy driver.

## Features

- Four virtual devices, each with 32 buttons, six axes, and a directional hat.
- Button pulse, press, and release actions; axis and hat value actions.
- Automatic server startup and shutdown with the Touch Portal plugin.
- Optional UDP forwarding to a server on another computer.
- Linux and Windows support. Windows support has not yet been tested with a real vJoy installation. macOS automatic startup is not configured.

## Requirements

- Touch Portal 4.0 or later on the computer running the plugin.
- Python 3 on the same computer. Touch Portal runs `/usr/bin/python3` on Linux and `py -3` on Windows.
- Linux: the `evdev` package for `/usr/bin/python3` and permission to access `/dev/uinput`.
- Windows: the vJoy driver, four configured vJoy devices, and `pyvjoy` for the Python selected by `py -3`.

## Installation

Use an existing `aigakira-virtual-joysticks.tpp` package, or create one using the [build guide](#build-from-source). The package is generated and is not included in the Git repository.

### Linux

1. Install your distribution's `python3-evdev` package, then check that the interpreter used by Touch Portal can import it:

	```sh
	/usr/bin/python3 -c 'import evdev; print("evdev is available")'
	```

2. Check that your user can write to `/dev/uinput`:

	```sh
	test -w /dev/uinput && echo 'uinput is writable' || echo 'uinput is unavailable or not writable'
	```

	If it is unavailable or not writable, configure the `uinput` module and device permissions using your distribution's instructions. Avoid running Touch Portal as root. Permissions for general input-device groups can also grant access to other input devices, so review them carefully.

3. Stop any separately running joystick server so UDP port `12100` is free.
4. In Touch Portal, open **Settings > Import plugin**, select `aigakira-virtual-joysticks.tpp`, and approve the plugin when prompted. Enable or restart it from the plug-in settings if needed.
5. Start your game after the plugin. The four Linux devices are named `aigakira-virtual-joystick-1` through `aigakira-virtual-joystick-4`.

### Windows

1. Install [vJoy](https://github.com/jshafer817/vJoy/releases) and the Configure vJoy utility. Driver installation may require administrator approval and a reboot; check compatibility with your Windows version first.
2. In Configure vJoy, enable devices 1-4. Give each at least 32 buttons, X, Y, Z, Rx, Ry and Rz axes, and one **continuous POV**. All four devices must be available and not acquired by another program. vJoy controls their names, which differ from the Linux names.
3. Install Python 3 and the Windows Python launcher, then install and verify `pyvjoy` using the same interpreter Touch Portal will use:

	```powershell
	py -3 -m pip install pyvjoy==1.0.1
	py -3 -c "import pyvjoy; print('pyvjoy is available')"
	```

	The published `pyvjoy` package selects an x86 or x64 interface DLL based on Python's architecture. Its documentation notes that a matching `vJoyInterface.dll` from the installed driver may be needed if loading fails.

4. Stop any separately running joystick server so UDP port `12100` is free. In Touch Portal, open **Settings > Import plugin**, select `aigakira-virtual-joysticks.tpp`, and approve the plugin when prompted. Enable or restart it from the plug-in settings if needed.
5. Check the devices with vJoy Monitor or the Windows game controller panel, then start your game.

## Build From Source

The build script creates a `.tpp` archive containing the plugin, both server implementations, and the license. It uses Python's standard library; building does not install Touch Portal, drivers, or runtime dependencies.

1. Obtain the project source and open a terminal in the project directory containing `build_plugin.py`.
2. Build the package:

	Linux:

	```sh
	python3 build_plugin.py
	```

	Windows:

	```powershell
	py -3 build_plugin.py
	```

3. Import the generated `aigakira-virtual-joysticks.tpp` file into Touch Portal as described above. Rebuild and re-import it after changing the plugin or server source.

### Tests

From the project directory on Linux, with `evdev` available to the Python interpreter, run:

```sh
python3 -m unittest -v test_aigakira_virtual_joysticks test_aigakira_windows
```

The Windows tests use simulated vJoy devices; they do not replace testing with a real Windows driver and game.

## Using The Plugin

1. In Touch Portal, add an action from **Aigakira Virtual Joysticks** to a button.
2. Select a device from 1-4 and choose the desired action:
	- **Joystick button:** Select a button from 1-32 and choose **Pulse**, **Press**, or **Release**. Pulse presses for 200 ms, then releases. Use Press and Release in the appropriate button-down and button-up flows for a held input.
	- **Set joystick axis:** Select an axis and enter a raw value. Values remain set until changed.
3. In your game, select the virtual device in a controller slot and bind its input to the desired control. For ETS2, start Touch Portal and the plugin before the game; restarting the plugin recreates the devices and may require restarting ETS2.

| Axis | Input range |
| --- | --- |
| `x`, `y`, `rx`, `ry` | -32768 to 32767 |
| `z`, `rz` | 0 to 255 |
| `hat_x`, `hat_y` | -1 to 1 |

On Windows, stick and trigger values are scaled to vJoy's 0-32767 range. The two hat axes combine into the first continuous POV, including diagonals.

## UDP Settings

The local server listens on `127.0.0.1:12100`. The plugin's **UDP Host** and **UDP Port** settings control where actions are sent; changing them does not change the local server's bind address or port. The local server still starts when a remote destination is configured.

For example, to run the Linux server on a separate machine and accept network connections:

```sh
python3 aigakira-virtual-joysticks.py --host 0.0.0.0 --port 12100
```

Set **UDP Host** in Touch Portal to that machine's IP address and **UDP Port** to `12100`. UDP commands are unauthenticated and delivery is not guaranteed. Anyone who can reach the server can control its virtual devices, so restrict network access with a firewall or use a trusted network.

Commands are UTF-8 JSON datagrams, for example:

```json
{"type":"button","device":1,"button":1,"action":"pulse"}
```

```json
{"type":"axis","device":1,"axis":"x","value":1000}
```

## Troubleshooting

- **Plugin or server does not start:** Check Touch Portal's log under `Aigakira Virtual Joysticks`: `~/.config/TouchPortal/log.txt` on Linux or `%APPDATA%\TouchPortal\log.txt` on Windows. Look for missing dependencies, device permissions or configuration, and port conflicts. Resolve the error and restart the plugin; a failed server is not automatically retried.
- **No action reaches the server:** Look for `Paired with Touch Portal` and `Sent` in the log. Check that the plugin is enabled, the button contains an Aigakira Virtual Joysticks action, and UDP Host and Port match the destination. UDP does not confirm delivery.
- **Button remains pressed:** A lost UDP release or a Press action without a corresponding Release can leave it held. Send Release first; use Pulse for ordinary taps.
- **Game detects the device but not the input:** Select it in an available controller slot, then bind using Pulse. For ETS2, try disabling Steam Input for the game and restarting it if binding still fails.
- **After updating:** Re-import the newly built package and restart the plugin. If an earlier installation used a different plugin folder, check that Touch Portal does not retain a duplicate.

## License

This project may be used, copied, modified, and distributed for noncommercial purposes only and without charge. Charging for the software, modified versions, or access to them is prohibited. Copies and modifications must retain the same terms. See [LICENSE](LICENSE); third-party dependencies have their own licenses. This custom license is source-available, not an open-source license.