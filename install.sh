#!/usr/bin/env bash
# Installs everything MetalEQ needs to run on Linux:
#   * system packages  - PyGObject, GStreamer (+ the "good" plugins that ship
#                        equalizer-nbands / pulsesrc / pulsesink), pactl
#   * PyQt6            - into your user site-packages (no venv: a venv would
#                        hide the system PyGObject the audio engine imports)
#   * launcher         - an app-menu entry plus an icon on your desktop (only
#                        after everything above verified OK; never replaces a
#                        launcher that points at a different MetalEQ install)
#
# Automatic system-package install is Debian/Ubuntu/Mint (apt) only. On other
# distros the script prints what to install and still does the PyQt6 step.
set -euo pipefail

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
APP_DIR=$PWD

APT_PACKAGES=(
    python3
    python3-pip
    python3-gi
    gir1.2-gstreamer-1.0
    gstreamer1.0-plugins-base
    gstreamer1.0-plugins-good
    pulseaudio-utils
)

say() { printf '\n==> %s\n' "$*"; }

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 was not found." >&2
fi

# ---- 1. system packages ---------------------------------------------------
say "Checking system packages"
if command -v apt-get >/dev/null 2>&1 && command -v dpkg-query >/dev/null 2>&1; then
    missing=()
    for pkg in "${APT_PACKAGES[@]}"; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            missing+=("$pkg")
        fi
    done

    if [ "${#missing[@]}" -eq 0 ]; then
        echo "All system packages are already installed."
    else
        echo "Missing: ${missing[*]}"
        if [ "$(id -u)" -eq 0 ]; then
            SUDO=()
        elif command -v sudo >/dev/null 2>&1; then
            SUDO=(sudo)
        else
            echo "Not root and sudo is not available. Install these as root:" >&2
            echo "    apt install ${missing[*]}" >&2
            exit 1
        fi
        "${SUDO[@]}" apt-get update
        "${SUDO[@]}" apt-get install -y "${missing[@]}"
    fi
else
    cat <<'EOF'
This isn't an apt-based system, so system packages are not installed
automatically. Make sure your distro's equivalents of these are installed:
    - Python 3 + pip
    - PyGObject (python3-gi / python-gobject / python3-gobject)
    - GStreamer 1.x introspection data (gir1.2-gstreamer-1.0 / gst-python)
    - GStreamer "base" and "good" plugins
    - pactl (pulseaudio-utils / libpulse); PipeWire users also need pipewire-pulse
EOF
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is still missing - install it and re-run this script." >&2
    exit 1
fi

# ---- 2. PyQt6 -------------------------------------------------------------
say "Installing PyQt6 (user site-packages)"
PIP_ARGS=(--user -r requirements.txt)
# Debian 12+/Ubuntu 23.04+/Mint 22 mark the system Python "externally managed"
# (PEP 668); --user installs then need --break-system-packages.
if python3 - <<'EOF'
import os, sys, sysconfig
sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")) else 1)
EOF
then
    PIP_ARGS+=(--break-system-packages)
fi
python3 -m pip install "${PIP_ARGS[@]}"

# ---- 3. verify ------------------------------------------------------------
say "Verifying"
status=0

python3 - <<'EOF' || status=1
import sys

problems = []

try:
    import PyQt6.QtWidgets  # noqa: F401
    print("  ok   PyQt6")
except Exception as exc:
    problems.append(f"PyQt6 failed to import: {exc}")

try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
    print("  ok   PyGObject + GStreamer", Gst.version_string().split()[-1])
    for element in ("pulsesrc", "pulsesink", "equalizer-nbands", "audiodynamic",
                    "volume", "audioconvert", "audioresample"):
        if Gst.ElementFactory.find(element) is None:
            problems.append(f"GStreamer element '{element}' not found "
                            "(install the gstreamer 'good' plugins)")
        else:
            print(f"  ok   gst element {element}")
except Exception as exc:
    problems.append(f"PyGObject/GStreamer unavailable: {exc}")

for p in problems:
    print("  FAIL", p)
sys.exit(1 if problems else 0)
EOF

if command -v pactl >/dev/null 2>&1; then
    echo "  ok   pactl"
else
    echo "  FAIL pactl not found (install pulseaudio-utils; PipeWire users also need pipewire-pulse)"
    status=1
fi

if [ "$status" -ne 0 ]; then
    say "Install finished with problems (see FAIL lines above)"
    exit 1
fi

# ---- 4. launcher + desktop icon -------------------------------------------
# Writes $2 (the .desktop text) to $1. An existing file is only refreshed if
# it already has our exact Exec= line ($3); otherwise it launches some other
# MetalEQ (or is unrelated) and is left untouched. $4 = "exec" also marks it
# executable + trusted, which Nemo/Cinnamon need to launch it from the desktop.
place_launcher() {
    local dest=$1 entry=$2 exec_line=$3 mode=${4:-}
    if [ -e "$dest" ] && ! grep -qxF "$exec_line" "$dest"; then
        echo "  left alone: $dest (it doesn't launch this copy of MetalEQ)"
        return 0
    fi
    printf '%s\n' "$entry" > "$dest" || return 1
    if [ "$mode" = "exec" ]; then
        chmod +x "$dest"
        if command -v gio >/dev/null 2>&1; then
            gio set "$dest" metadata::trusted true 2>/dev/null || true
        fi
    fi
    echo "  created: $dest"
}

install_launchers() {
    local run_sh="$APP_DIR/run.sh"
    local icon="$APP_DIR/equalizer/icons/audio-equalizer-256.png"

    # Exec= needs quoting/escaping for these; not worth getting subtly wrong.
    case "$run_sh" in
        *[\"\`\$\\]*)
            echo "  skipped: the install path contains a quote, backtick, \$ or backslash"
            return 0 ;;
    esac
    local exec_line="Exec=\"${run_sh//%/%%}\""   # quoted, so spaces are fine

    local entry
    entry=$(cat <<EOF
[Desktop Entry]
Type=Application
Name=MetalEQ
Comment=Free system-wide audio equalizer, designed for metal
$exec_line
Icon=$icon
Terminal=false
Categories=AudioVideo;Audio;Mixer;
StartupNotify=false
EOF
)

    local apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$apps_dir" || return 1
    place_launcher "$apps_dir/metal-eq.desktop" "$entry" "$exec_line"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$apps_dir" 2>/dev/null || true
    fi

    local desktop_dir
    desktop_dir=$(xdg-user-dir DESKTOP 2>/dev/null || true)
    [ -n "$desktop_dir" ] || desktop_dir="$HOME/Desktop"
    # xdg-user-dir answers $HOME when the desktop folder is disabled.
    if [ "$desktop_dir" != "$HOME" ] && [ -d "$desktop_dir" ]; then
        place_launcher "$desktop_dir/metal-eq.desktop" "$entry" "$exec_line" exec
    else
        echo "  no desktop folder found - skipped the desktop icon"
    fi
}

say "Creating launcher and desktop icon"
install_launchers || echo "  could not create the launcher (not fatal - ./run.sh still works)"

say "Done. Start MetalEQ from your app menu / desktop icon, or with:  ./run.sh"
