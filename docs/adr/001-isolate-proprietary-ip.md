# ADR-001: Proprietary IP Isolation Contract

**Status:** Proposed  
**Date:** 2026-09-01  
**Owner:** Nexus Signalworks (principal architect)  
**Reviewers:** [to be assigned]  
**Supersedes:** None  

---

## Context

BetterStreamFX ships as a GPL-3.0-or-later project but contains code contributed by Nexus Signalworks that the principal intends to keep available for potential commercial licensing or relicensing outside the GPL boundary. This ADR defines the isolation contract that keeps that proprietary code from contaminating the GPL core, and the CI gate that enforces it on every PR.

The boundary was identified through an audit (see parent task). The proprietary asset is currently:

- **File:** `source/util/util-dbscan.hpp`
- **Copyright holder:** Nexus Signalworks
- **License status:** SPDX header says GPL-3.0-or-later, but the file is treated as proprietary for isolation purposes to preserve future relicensing optionality.

The recommended structural isolation is to move this file into a dedicated `source/nexus/` tree and gate it behind a `BUILD_PROPRIETARY` CMake option. Until the move is completed, the CI gate operates on the existing path.

---

## Decision

1. **Boundary.** A single file — `source/util/util-dbscan.hpp` — is designated as the proprietary entry point. All other source files, build system files, third-party libraries, and components are part of the GPL core.

2. **Include boundary.** The GPL core must not `#include` `source/util/util-dbscan.hpp`, directly or indirectly. Any GPL core code that needs DBSCAN-like functionality must either be reimplemented under GPL-compatible terms or use a shim that is only compiled in when `BUILD_PROPRIETARY=ON`.

3. **Link boundary.** The GPL core binary must not link against any object code that transitively depends on `source/util/util-dbscan.hpp`. The proprietary implementation is compiled into a separate static library (`nexus_proprietary`) gated behind `BUILD_PROPRIETARY=ON`.

4. **Allowed interaction pattern.** Communication between the GPL core and the proprietary layer is restricted to abstract interfaces defined in GPL-owned headers. The proprietary layer may implement those interfaces, but the GPL core must never include a proprietary header.

5. **Build gate.** CMake must support a `BUILD_PROPRIETARY` option (default `OFF`). When `OFF`, the `source/nexus/` directory (or the current proprietary path, until the move is completed) is not added to the build, and no proprietary symbols are compiled into the GPL binary.

6. **CI enforcement.** Every PR and push to a branch triggers a compliance job that:
   - Builds with `BUILD_PROPRIETARY=OFF`.
   - Runs a script that scans the GPL binary and source tree for forbidden include paths and proprietary symbols.
   - Fails the job if any violation is found.

7. **Ownership.** The proprietary layer is owned by Nexus Signalworks. The GPL core is owned by the project maintainers under GPL-3.0-or-later. No contributor may move a file across the boundary without a documented decision recorded in an ADR.

---

## Compliance Gate

The gate is implemented as a GitHub Actions workflow step (see `.github/workflows/compliance.yml`) and a standalone script (`tools/check-proprietary-boundary.sh`).

### What the gate checks

1. **Source scan.** Greps all `.cpp`, `.c`, `.hpp`, and `.h` files in the GPL core for any `#include` of the proprietary path. The current forbidden include path is:
   - `source/util/util-dbscan.hpp`
   - Any path under `source/nexus/` once the move is completed.

2. **Symbol scan.** After building with `BUILD_PROPRIETARY=OFF`, runs `nm` or `objdump` on the resulting binary and greps for mangled or unmangled symbols that originate from the proprietary file. The expected symbol prefix is derived from the proprietary file's function names (e.g., `dbscan_`).

3. **Build configuration check.** Verifies that `BUILD_PROPRIETARY` is not accidentally set to `ON` in any CI matrix entry for the GPL build.

### Failure behavior

If any check fails, the job exits with a non-zero code and the PR is blocked. The failure log must identify the file, line, and symbol that caused the violation so the author can remediate.

### Test PR

A test PR that intentionally includes `source/util/util-dbscan.hpp` from a GPL core file must be created to confirm the gate fires. The test PR should:
- Add a `#include "source/util/util-dbscan.hpp"` to a GPL core source file.
- Attempt to build with `BUILD_PROPRIETARY=OFF`.
- Expect the compliance job to fail with a clear violation message.

---

## Implementation Plan

1. Add `BUILD_PROPRIETARY` option to `CMakeLists.txt` (OFF by default).
2. Move `source/util/util-dbscan.hpp` to `source/nexus/util/dbscan.hpp`.
3. Add `source/nexus/` as a conditional subdirectory in CMake, gated on `BUILD_PROPRIETARY=ON`, producing a `nexus_proprietary` static library.
4. Ship `tools/check-proprietary-boundary.sh`.
5. Ship `.github/workflows/compliance.yml`.
6. Document the gate in this ADR (done).
7. Create a test PR that violates the boundary and confirm the gate blocks it.

---

## Notes

- The current SPDX identifier on `util-dbscan.hpp` says GPL-3.0-or-later. Treating it as proprietary is a forward-looking isolation measure, not a retroactive license change. If the intent is to keep the file GPL permanently, no isolation is required, and this ADR should be superseded.
- The `source/util/` directory contains other GPL files. Only `util-dbscan.hpp` is moved; the remaining files stay in place.
- The compliance script must be kept in sync with the actual proprietary path as the repository evolves. Any change to the proprietary asset list requires an ADR update.

---

## References

- Boundary specification: `BOUNDARY_SPEC.md` (parent task output)
- Source audit: parent task `t_8cba3016`
