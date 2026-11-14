#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s [--check]\n' "${0##*/}"
    printf 'Install Linux dependencies, or check them without making changes.\n'
}

if [[ $# -gt 1 ]]; then
    usage >&2
    exit 2
fi
case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --check) check_only=1 ;;
    '') check_only=0 ;;
    *) usage >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != Linux ]]; then
    printf 'This installer only supports Linux.\n' >&2
    exit 1
fi

if (( ! check_only )); then
    if [[ ! -r /etc/os-release ]]; then
        printf 'Cannot detect Linux distribution: /etc/os-release is missing.\n' >&2
        exit 1
    fi
    . /etc/os-release
    distro=" ${ID:-} ${ID_LIKE:-} "
    if [[ $distro == *' arch '* ]] || [[ $distro == *' cachyos '* ]]; then
        packages=(pacman -S --needed python python-evdev)
    elif [[ $distro == *' debian '* ]] || [[ $distro == *' ubuntu '* ]]; then
        packages=(apt-get install python3 python3-evdev)
    elif [[ $distro == *' fedora '* ]] || [[ $distro == *' rhel '* ]]; then
        packages=(dnf install python3 python3-evdev)
    elif [[ $distro == *' suse '* ]] || [[ $distro == *' opensuse '* ]]; then
        packages=(zypper install python3 python3-evdev)
    else
        printf 'Unsupported distribution: %s. Install Python 3 and the system evdev package manually.\n' "${ID:-unknown}" >&2
        exit 1
    fi

    printf 'Installing dependencies using %s.\n' "${packages[0]}"
    if (( EUID == 0 )); then
        "${packages[@]}"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "${packages[@]}"
    else
        printf 'sudo is not available. Run this script as root to install packages.\n' >&2
        exit 1
    fi
fi

status=0
if /usr/bin/python3 -c 'import evdev' >/dev/null 2>&1; then
    printf 'OK: /usr/bin/python3 can import evdev.\n'
else
    printf 'ERROR: /usr/bin/python3 cannot import evdev.\n' >&2
    status=1
fi

if [[ -w /dev/uinput ]]; then
    printf 'OK: /dev/uinput is writable by the current user.\n'
else
    printf 'WARNING: /dev/uinput is missing or not writable by the current user.\n' >&2
    printf 'Configure the uinput module and device permissions for the Touch Portal user.\n' >&2
    status=1
fi

if (( EUID == 0 )); then
    printf 'NOTE: Device access was checked as root; run --check as the Touch Portal user too.\n'
fi
exit "$status"