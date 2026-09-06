"""Dual-backend regression harness for Origin.

Runs every ``.or`` program in ``tests_fixtures/`` through BOTH backends and
compares their stdout:

    VM mode          : python runner.py <file.or>
    Interpreter mode : python runner.py i <file.or>

Warnings (e.g. let-inference nudges) go to stderr, so stdout is the only
signal compared. A program is reported as passing only if both backends
agree on stdout and both exit successfully.

Usage:
    python test_suite.py                # run all fixtures, summary only
    python test_suite.py --verbose      # show per-fixture stdout on mismatch
    python test_suite.py --only name    # run a single fixture by filename
"""

import argparse
import os
import subprocess
import sys

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests_fixtures")
TIMEOUT_SECONDS = 30


def run_backend(python, runner, fixture, mode):
    """Run one fixture in one backend; return (stdout, stderr, returncode)."""
    cmd = [python, runner, fixture]
    if mode == "interp":
        cmd.insert(2, "i")
    proc = subprocess.run(
        cmd,
        cwd=os.path.dirname(runner),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    return proc.stdout, proc.stderr, proc.returncode


def normalize(text):
    """Normalize stdout for comparison (strip trailing whitespace per line)."""
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--only", metavar="FILE", help="run a single fixture")
    args = parser.parse_args()

    fixtures = sorted(f for f in os.listdir(FIXTURES_DIR) if f.endswith(".or"))
    if args.only:
        if args.only not in fixtures:
            sys.exit(f"no fixture named '{args.only}' in {FIXTURES_DIR}")
        fixtures = [args.only]

    if not fixtures:
        sys.exit(f"no .or fixtures found in {FIXTURES_DIR}")

    python = sys.executable
    runner = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner.py")

    passed = []
    failed = []
    for name in fixtures:
        fixture = os.path.join(FIXTURES_DIR, name)
        try:
            vm_out, vm_err, vm_rc = run_backend(python, runner, fixture, "vm")
            int_out, int_err, int_rc = run_backend(python, runner, fixture, "interp")
        except subprocess.TimeoutExpired:
            failed.append((name, "TIMEOUT", ""))
            continue

        vm_norm, int_norm = normalize(vm_out), normalize(int_out)
        ok = vm_rc == 0 and int_rc == 0 and vm_norm == int_norm
        status = "PASS" if ok else "FAIL"

        if ok:
            passed.append(name)
        else:
            reason = []
            if vm_rc != 0:
                reason.append(f"vm rc={vm_rc}")
            if int_rc != 0:
                reason.append(f"interp rc={int_rc}")
            if vm_norm != int_norm:
                reason.append("stdout mismatch")
            failed.append((name, " | ".join(reason), vm_out))

        if args.verbose or not ok:
            print(f"[{status}] {name}")
            if not ok and args.verbose:
                if vm_norm != int_norm:
                    print("  --- VM stdout ---")
                    print(vm_out)
                    print("  --- Interp stdout ---")
                    print(int_out)
                if vm_rc != 0:
                    print("  --- VM stderr ---")
                    print(vm_err)
                if int_rc != 0:
                    print("  --- Interp stderr ---")
                    print(int_err)

    print()
    print(f"{len(passed)} passed, {len(failed)} failed, {len(fixtures)} total")
    for name, reason, _ in failed:
        print(f"  FAIL {name}: {reason}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


