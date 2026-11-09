#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# check-proprietary-boundary.sh — GPL/proprietary isolation compliance gate.
#
# Builds with BUILD_PROPRIETARY=OFF and verifies that:
#   1. No GPL-core source file includes a proprietary header.
#   2. No proprietary symbols appear in the resulting binary.
#
# Exits 0 on success, 1 on violation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "")"

if [[ -z "$REPO_ROOT" ]]; then
  echo "ERROR: not running inside a git repository; cannot determine REPO_ROOT"
  exit 1
fi

# ---- Configuration ----
# Proprietary source path(s). Update this list when the proprietary asset moves
# (see ADR-001). The patterns are file paths relative to REPO_ROOT.
FORBIDDEN_SOURCE_PATTERNS=(
  "source/util/util-dbscan.hpp"
  "source/nexus/"
)

# ERE alternation of the forbidden source patterns.
# NOTE: ${arr[*]} space-joins elements, which produces a literal-space regex
# that can never match an include path. Join with '|' instead.
FORBIDDEN_SOURCE_RE="$(printf '%s|' "${FORBIDDEN_SOURCE_PATTERNS[@]}")"
FORBIDDEN_SOURCE_RE="${FORBIDDEN_SOURCE_RE%|}"

# Symbol patterns to reject in the GPL binary. Update when the proprietary
# symbol table changes. These are matched with grep -i against nm/objdump
# output, so they should be distinctive substrings of the mangled or unmangled
# symbol names.
FORBIDDEN_SYMBOL_PATTERNS=(
  "dbscan"
)
FORBIDDEN_SYMBOL_RE="$(printf '%s|' "${FORBIDDEN_SYMBOL_PATTERNS[@]}")"
FORBIDDEN_SYMBOL_RE="${FORBIDDEN_SYMBOL_RE%|}"

# Build configuration for the compliance build.
BUILD_DIR="${BUILD_DIR:-build/compliance}"
CMAKE_GENERATOR="${CMAKE_GENERATOR:-Unix Makefiles}"
BUILD_TYPE="${BUILD_TYPE:-Release}"

# ---- Helpers ----

failure() {
  echo "COMPLIANCE_VIOLATION: $*"
  exit 1
}

info() {
  echo "INFO: $*"
}

# ---- Source scan ----

info "Scanning source tree for forbidden include paths..."
violations=0
while IFS= read -r -d '' file; do
  rel="${file#$REPO_ROOT/}"
  if grep -nE '#include[[:space:]]+["<]' "$file" | grep -iE "$FORBIDDEN_SOURCE_RE" > /tmp/proprietary-include-violation.tmp; then
    echo "=== Violation in $rel ==="
    cat /tmp/proprietary-include-violation.tmp
    rm -f /tmp/proprietary-include-violation.tmp
    violations=$((violations + 1))
  fi
done < <(git -C "$REPO_ROOT" ls-files -z '*.cpp' '*.c' '*.hpp' '*.h' '*.cc' '*.hh' | while IFS= read -r -d '' f; do printf '%s\0' "$REPO_ROOT/$f"; done)

if [[ "$violations" -gt 0 ]]; then
  failure "found $violations source file(s) that include a proprietary path"
fi

# ---- Build with BUILD_PROPRIETARY=OFF ----

info "Configuring compliance build with BUILD_PROPRIETARY=OFF..."
cmake -S "$REPO_ROOT" -B "$BUILD_DIR" \
  -G "$CMAKE_GENERATOR" \
  -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
  -DBUILD_PROPRIETARY=OFF \
  -DCMAKE_SKIP_INSTALL_ALL_DEPENDENCY=ON \
  ${CMAKE_EXTRA_ARGS:-}

info "Building compliance target..."
cmake --build "$BUILD_DIR" --config "$BUILD_TYPE" --target StreamFX -j"$(nproc 2>/dev/null || echo 2)"

# ---- Binary symbol scan ----

info "Scanning built binary for forbidden proprietary symbols..."
binary="$(find "$BUILD_DIR" -type f \( -name 'StreamFX.dll' -o -name 'StreamFX.so' -o -name 'StreamFX.dylib' -o -name 'StreamFX' \) -print -quit 2>/dev/null || true)"

if [[ -z "$binary" ]]; then
  echo "WARNING: no StreamFX binary found under $BUILD_DIR; skipping symbol scan"
else
  info "Inspecting: $binary"
  if command -v nm >/dev/null 2>&1; then
    nm -C "$binary" 2>/dev/null | grep -iE "$FORBIDDEN_SYMBOL_RE" > /tmp/proprietary-symbol-violation.tmp || true
  elif command -v objdump >/dev/null 2>&1; then
    objdump -t "$binary" 2>/dev/null | grep -iE "$FORBIDDEN_SYMBOL_RE" > /tmp/proprietary-symbol-violation.tmp || true
  else
    echo "WARNING: neither nm nor objdump found; skipping symbol scan"
  fi

  if [[ -s /tmp/proprietary-symbol-violation.tmp ]]; then
    echo "=== Symbol violation ==="
    cat /tmp/proprietary-symbol-violation.tmp
    rm -f /tmp/proprietary-symbol-violation.tmp
    failure "binary contains proprietary symbols"
  fi
  rm -f /tmp/proprietary-symbol-violation.tmp
fi

# ---- Build flag verification ----

info "Verifying BUILD_PROPRIETARY is OFF in CI matrix configuration..."
if grep -rniE 'BUILD_PROPRIETARY[[:space:]]*=[[:space:]]*ON' "$BUILD_DIR" > /tmp/proprietary-flag-violation.tmp 2>/dev/null; then
  echo "=== Flag violation ==="
  cat /tmp/proprietary-flag-violation.tmp
  rm -f /tmp/proprietary-flag-violation.tmp
  failure "BUILD_PROPRIETARY=ON detected in build output/configuration"
fi
rm -f /tmp/proprietary-flag-violation.tmp

info "Compliance gate passed."
exit 0