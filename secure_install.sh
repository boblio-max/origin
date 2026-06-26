#!/usr/bin/env bash
# Origin Language Secure Installer (macOS / Linux)
#
# Mirrors secure_install.ps1:
#   1. Verifies the SHA-256 of the Origin binary against SHA256SUMS
#      (binary-swapping protection against tampered zips).
#   2. Installs to "$HOME/.origin/bin" (XDG-aware on Linux).
#   3. Prepends the install dir to the user PATH via the active shell
#      rc file (path-hijacking protection: our dir resolves before
#      /usr/bin / /usr/local/bin).
#
# Usage:
#     chmod +x secure_install.sh
#     ./secure_install.sh [binary_name]
#
# The default binary name is "origin". Pass "origin.exe" to override.

set -euo pipefail

# --- Locate bundle files relative to this script -----------------------------
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
EXE_NAME="${1:-origin}"
EXE_PATH="${SCRIPT_DIR}/${EXE_NAME}"
SUMS_PATH="${SCRIPT_DIR}/SHA256SUMS"

# --- Install location (XDG-aware on Linux, ~/.origin/bin elsewhere) ----------
if [[ -n "${XDG_DATA_HOME:-}" ]]; then
    INSTALL_DIR="${XDG_DATA_HOME}/origin/bin"
else
    INSTALL_DIR="${HOME}/.origin/bin"
fi

# --- ANSI colors (no-op if not a TTY) ----------------------------------------
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1 && [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    C_CYAN="$(tput setaf 6)"; C_GREEN="$(tput setaf 2)"; C_YELLOW="$(tput setaf 3)"
    C_RED="$(tput setaf 1)"; C_RESET="$(tput sgr0)"
else
    C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

echo "${C_CYAN}--- Secure Origin Language Installer ---${C_RESET}"

# --- Pre-flight checks --------------------------------------------------------
if [[ ! -f "${EXE_PATH}" ]]; then
    echo "${C_RED}Error: could not find ${EXE_NAME} in ${SCRIPT_DIR}.${C_RESET}" >&2
    exit 1
fi

if [[ ! -f "${SUMS_PATH}" ]]; then
    echo "${C_RED}Error: SHA256SUMS not found next to the binary.${C_RESET}" >&2
    echo "The installer refuses to proceed without an integrity manifest." >&2
    exit 1
fi

# --- 1. Integrity check -------------------------------------------------------
echo "${C_CYAN}[*] Verifying ${EXE_NAME} integrity against tampering...${C_RESET}"
ACTUAL_HASH="$(shasum -a 256 "${EXE_PATH}" 2>/dev/null \
    || sha256sum "${EXE_PATH}" 2>/dev/null \
    || { echo "${C_RED}Error: no SHA-256 tool found (install shasum or coreutils).${C_RESET}" >&2; exit 1; })"
ACTUAL_HASH="$(echo "${ACTUAL_HASH}" | awk '{print $1}' | tr 'A-Z' 'a-z')"

EXPECTED_HASH="$(grep -iE "^[0-9a-f]{64}[[:space:]]+(\*?${EXE_NAME})$" "${SUMS_PATH}" \
    | awk '{print $1}' | tr 'A-Z' 'a-z' || true)"

if [[ -z "${EXPECTED_HASH}" ]]; then
    echo "${C_RED}[!!!] CRITICAL SECURITY ALERT [!!!]${C_RESET}" >&2
    echo "${C_RED}No checksum entry found for '${EXE_NAME}' in SHA256SUMS.${C_RESET}" >&2
    echo "Refusing to install an unverified binary." >&2
    exit 1
fi

if [[ "${ACTUAL_HASH}" != "${EXPECTED_HASH}" ]]; then
    echo "" >&2
    echo "${C_RED}[!!!] CRITICAL SECURITY ALERT [!!!]${C_RESET}" >&2
    echo "${C_RED}The ${EXE_NAME} file has been modified, corrupted, or replaced!${C_RESET}" >&2
    echo "${C_YELLOW}This is a sign of a potential Binary Swapping attack (Trojan).${C_RESET}" >&2
    echo "Installation aborted. Please download a fresh, official copy." >&2
    exit 1
fi
echo "${C_GREEN}[+] Binary integrity verified successfully.${C_RESET}"

# --- 2. Install directory ----------------------------------------------------
mkdir -p "${INSTALL_DIR}"
echo "${C_CYAN}[*] Installing Origin to ${INSTALL_DIR}...${C_RESET}"
cp -f "${EXE_PATH}" "${INSTALL_DIR}/origin"
chmod 0755 "${INSTALL_DIR}/origin"

# --- 3. PATH prepend (path-hijacking protection) ----------------------------
# Detect the user's login shell rc file. We prepend rather than append so the
# Origin binary resolves before any /usr/bin or /usr/local/bin impostor.
SHELL_NAME="$(basename "${SHELL:-/bin/sh}")"
case "${SHELL_NAME}" in
    bash) RC_FILE="${HOME}/.bashrc" ;;
    zsh)  RC_FILE="${HOME}/.zshrc"  ;;
    fish) RC_FILE="${HOME}/.config/fish/config.fish" ;;
    ksh|sh|dash|ash) RC_FILE="${HOME}/.profile" ;;
    *)    RC_FILE="${HOME}/.profile" ;;
esac

PATH_LINE="export PATH=\"${INSTALL_DIR}:\$PATH\""
FISH_LINE="set -gx PATH ${INSTALL_DIR} \$PATH"

echo "${C_CYAN}[*] Securing shell PATH in ${RC_FILE}...${C_RESET}"
mkdir -p "$(dirname "${RC_FILE}")"
touch "${RC_FILE}"

if [[ "${SHELL_NAME}" == "fish" ]]; then
    if ! grep -Fq "${INSTALL_DIR}" "${RC_FILE}"; then
        printf '\n# Added by Origin secure installer\n%s\n' "${FISH_LINE}" >> "${RC_FILE}"
    fi
else
    if ! grep -Fq "${INSTALL_DIR}" "${RC_FILE}"; then
        printf '\n# Added by Origin secure installer\n%s\n' "${PATH_LINE}" >> "${RC_FILE}"
    fi
fi

# Make the change effective in the current session too.
export PATH="${INSTALL_DIR}:${PATH}"
hash -r 2>/dev/null || true
echo "${C_GREEN}[+] Successfully secured and added to PATH!${C_RESET}"

echo ""
echo "${C_GREEN}--- Installation Complete! ---${C_RESET}"
echo "Open a new terminal and type 'origin' to start."
