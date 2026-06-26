#!/usr/bin/env bash
# Local cross-platform build helper for the Origin language.
#
# Builds the current host's Origin binary and zips it alongside the
# matching secure_install.{sh,ps1} and a SHA256SUMS file. Useful for
# testing the bundle locally before pushing to CI.
#
# Usage:
#     ./build_installer.sh           # auto-detects host OS
#     ./build_installer.sh macos     # builds origin.spec.macos
#     ./build_installer.sh linux
#     ./build_installer.sh windows   # requires Windows + origin.spec
set -euo pipefail

case "${1:-$(uname -s | tr 'A-Z' 'a-z')}" in
    darwin|macos)
        SPEC="origin.spec.macos"
        BINARY="origin"
        ARCHIVE="OriginInstaller-macos-universal.zip"
        ;;
    linux)
        SPEC="origin.spec.linux"
        BINARY="origin"
        ARCHIVE="OriginInstaller-linux-x64.zip"
        ;;
    mingw*|msys*|cygwin*|windows)
        SPEC="origin.spec"
        BINARY="origin.exe"
        ARCHIVE="OriginInstaller-windows-x64.zip"
        ;;
    *)
        echo "Unknown OS: ${1:-$(uname -s)}" >&2
        echo "Pass one of: macos | linux | windows" >&2
        exit 1
        ;;
esac

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "${SCRIPT_DIR}"

echo "[*] Cleaning previous build artifacts..."
rm -rf build dist stage "${ARCHIVE}"

echo "[*] Running PyInstaller with ${SPEC}..."
pyinstaller --noconfirm --clean "${SPEC}"

echo "[*] Staging installer bundle..."
mkdir -p stage
cp "dist/${BINARY}" "stage/${BINARY}"
[[ -d dist/lib ]] && cp -R dist/lib stage/lib
[[ -d dist/_internal ]] && cp -R dist/_internal stage/_internal || true
if [[ "${BINARY}" == *.exe ]]; then
    cp secure_install.ps1 stage/secure_install.ps1
else
    cp secure_install.sh stage/secure_install.sh
    chmod +x stage/secure_install.sh
fi

echo "[*] Writing SHA256SUMS..."
( cd stage && sha256sum "${BINARY}" > SHA256SUMS )

echo "[*] Creating ${ARCHIVE}..."
if command -v zip >/dev/null 2>&1; then
    ( cd stage && zip -r "../${ARCHIVE}" . )
else
    python -m zipfile -c "${ARCHIVE}" stage/*
fi

echo "[+] Built ${ARCHIVE}"
echo "    Run secure_install.sh (or .ps1) inside the zip to install."
