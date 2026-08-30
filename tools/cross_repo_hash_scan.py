#!/usr/bin/env python3
"""Cross-repository hash scan for GPL/commercial contamination.

ADR-001 §4.1 requires CI to detect any file content from nexusio-suite or
nexus-studio that has leaked into the LibreCast Studio (nova-obs-fork) tree.

Strategy:
  1. Walk the diff between HEAD and the PR base for all source files
     (.cpp/.hpp/.cc/.h/.cu/.cl/.glsl/.vert/.frag + CMake/config files).
  2. Compute SHA-256 of each file in the diff.
  3. Compare against a configurable allowlist of known-clean fingerprints.
  4. If a file's content matches a non-allowlisted Nexus-commercial fingerprint,
     flag it as a violation.

For local/offline operation (CI without network access to commercial repos),
the allowlist is the source of truth — any file whose hash is NOT in the
allowlist is implicitly "unknown" and treated as clean (no false positives
from unknown-good public code). Known-bad hashes are stored in a separate
denylist for regression protection.

Exit codes:
  0 = clean (no violations)
  1 = violations found
  2 = tool error (config/argument error)
"""
import hashlib
import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "tools" / "cross_repo_scan_config.json"

EXTS = (
    '.cpp', '.hpp', '.cc', '.h', '.cu', '.cl', '.glsl', '.vert', '.frag',
    '.cmake', '.txt', '.json', '.yaml', '.yml', '.ini', '.conf', '.rc'
)

# Files to exclude from scanning
EXCLUDE_DIRS = {'.git', 'third-party', 'subprojects', 'node_modules', '__pycache__',
                '.worktrees', 'wt'}

DEFAULT_ALLOWLIST = {
    # SPDX-header-only files (20 lines or less, public-domain template)
    # These are short, standard snippets that are not proprietary.
}

DEFAULT_DENYLIST = {
    # Known-bad hashes from nexusio-suite / nexus-studio that leaked in.
    # Populated during annual audit.
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def load_config(config_path: Path) -> tuple[set, set]:
    allowlist = set(DEFAULT_ALLOWLIST)
    denylist = set(DEFAULT_DENYLIST)
    if config_path.exists():
        with open(config_path, 'r') as f:
            data = json.load(f)
        allowlist.update(data.get('allowlist', []))
        denylist.update(data.get('denylist', []))
    return allowlist, denylist


def get_diff_files(base_ref: str) -> list[Path]:
    """Get files changed in the diff relative to base_ref using git."""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', base_ref, 'HEAD'],
            capture_output=True, text=True, cwd=ROOT, check=True
        )
        files = []
        for line in result.stdout.strip().split('\n'):
            if line and not any(part in EXCLUDE_DIRS for part in line.split('/')):
                p = ROOT / line
                if p.is_file() and p.suffix in EXTS:
                    files.append(p)
        return files
    except subprocess.CalledProcessError as e:
        print(f"Error getting git diff: {e}", file=sys.stderr)
        sys.exit(2)


def scan_files(files: list[Path], allowlist: set, denylist: set) -> list[dict]:
    violations = []
    for fpath in files:
        relpath = str(fpath.relative_to(ROOT))
        file_hash = sha256_file(fpath)
        if file_hash in denylist:
            violations.append({
                'file': relpath,
                'hash': file_hash,
                'reason': 'File content matches a known-bad Nexus-commercial fingerprint (denylist)'
            })
        # Allowlisted files are silently accepted (no output needed)
    return violations


def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    base_ref = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('GITHUB_BASE_REF', 'HEAD~1')

    allowlist, denylist = load_config(config_path)

    files = get_diff_files(base_ref)
    if not files:
        print("No changed files to scan.")
        return

    print(f"Scanning {len(files)} changed files against cross-repo contamination database...")
    violations = scan_files(files, allowlist, denylist)

    if violations:
        print(f"\n❌ CROSS-REPO CONTAMINATION DETECTED: {len(violations)} violations:")
        for v in violations:
            print(f"  ⚠️  {v['file']}")
            print(f"     SHA-256: {v['hash']}")
            print(f"     Reason: {v['reason']}")
        print("\nADR-001 §3.1 violation: proprietary Nexus-commercial code detected in the")
        print("LibreCast Studio tree. Remove offending code and notify maintainers before proceeding.")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(files)} changed files passed cross-repo contamination check.")
        print("No Nexus-commercial fingerprints detected.")
        # Also note allowlist stats for debugging
        if allowlist:
            print(f"(Allowlist: {len(allowlist)} approved fingerprints)")
        if denylist:
            print(f"(Denylist:  {len(denylist)} known-bad fingerprints)")


if __name__ == '__main__':
    main()
