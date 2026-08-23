#!/usr/bin/env bash
#
# Origin Programming Language — single-command install for Raspberry Pi
#   curl -sSL https://origin.dev/install.sh | bash
#   wget -qO- https://origin.dev/install.sh | bash
#
set -euo pipefail

ORIGIN_VERSION="1.7.20"
INSTALL_DIR="${ORIGIN_HOME:-$HOME/.origin}"
BIN_DIR="$INSTALL_DIR/bin"
PKG_DIR="$INSTALL_DIR/lib"

# --- Colors ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

info()  { printf "${BLUE}%s${NC}\n" "$*"; }
ok()    { printf "${GREEN}✓ %s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}⚠ %s${NC}\n" "$*"; }
err()   { printf "${RED}✗ %s${NC}\n" "$*"; exit 1; }

# --- Detect Pi ---
ARCH=$(uname -m)
case "$ARCH" in
    aarch64|armv7l|armv6l)  PI=1  ;;
    x86_64|amd64)           PI=0  ;;
    *)                      warn "Untested architecture: $ARCH — proceeding anyway"; PI=0 ;;
esac

info "Origin v$ORIGIN_VERSION installer for $ARCH"

# --- Check Python ---
PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        PY_VER=$($cmd --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        MAJOR=${PY_VER%.*}; MINOR=${PY_VER#*.}
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    info "Installing Python 3.11..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3 python3-pip python3-venv
        PYTHON=python3
    else
        err "Python 3.10+ required. Install it first, then re-run."
    fi
fi
ok "Python: $($PYTHON --version 2>&1)"

# --- Install via pip ---
info "Installing Origin..."
mkdir -p "$PKG_DIR"

# Option A: Install from PyPI
$PYTHON -m pip install --user "origin-or==$ORIGIN_VERSION" 2>/dev/null || {
    # Option C: Install directly from GitHub
    # Option C: Local pip install from the repo
    warn "GitHub install failed — trying direct install"
    TMPDIR=$(mktemp -d)
    cd "$TMPDIR"
    curl -sSL "https://github.com/boblio-max/origin/archive/refs/tags/v$ORIGIN_VERSION.tar.gz" | tar xz --strip=1
    $PYTHON -m pip install --user . 2>/dev/null || {
        warn "Falling back to manual install"
        mkdir -p "$PKG_DIR/origin" "$BIN_DIR"
        cp -r origin/* "$PKG_DIR/origin/"
        cat > "$BIN_DIR/origin" << 'SCRIPT'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.expanduser("~/.origin/lib"))
from origin.runner import run_origin
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Origin Programming Language v1.7.19")
        print("Usage: origin <file.or>")
        sys.exit(1)
    run_origin(sys.argv[1])
SCRIPT
        chmod +x "$BIN_DIR/origin"
    }
    rm -rf "$TMPDIR"
}

# --- Add to PATH ---
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]] && [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_RC=""
    case "${SHELL:-}" in
        */bash) SHELL_RC="$HOME/.bashrc" ;;
        */zsh)  SHELL_RC="$HOME/.zshrc"  ;;
        */fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
    esac
    if [ -n "$SHELL_RC" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        ok "Added ~/.local/bin to PATH in $SHELL_RC"
    else
        warn "Add ~/.local/bin to your PATH manually"
    fi
fi

# --- Install Pi hardware deps ---
if [ "$PI" = "1" ]; then
    info "Installing Raspberry Pi hardware packages..."
    $PYTHON -m pip install --user "RPi.GPIO" "adafruit-circuitpython-servokit" "smbus2" 2>/dev/null || \
        warn "Could not install Pi hardware packages (install manually: pip install RPi.GPIO adafruit-circuitpython-servokit smbus2)"
fi

ok "Origin v$ORIGIN_VERSION installed!"
info "Run: origin hello.or"
