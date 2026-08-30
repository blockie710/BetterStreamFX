# ADR-001: Commercial Derivative Boundary for LibreCast Studio (GPLv3-or-later)

> **Status:** Accepted  
> **Date:** 2026-08-30  
> **Task ID:** ISS-02  
> **Author:** Nexus Orchestrator (Nexus / Chief of Staff)  
> **Related:** `LICENSE-CHECK.md` §4, `docs/LICENSE_AUDIT.md` §Commercial-Derivative Flag  

---

## 1. Context & Problem

**LibreCast Studio** (repository: `nova-obs-fork`) is a community-driven fork of the OBS Studio ecosystem licensed under **GNU GPL v3 (or later)** (`SPDX: GPL-3.0-or-later`). At the same time, the broader **Nexus ecosystem** maintains a proprietary commercial software tree (`nexusio-suite`, `nexus-studio`, etc.) that is closed-source and distributed under commercial license terms.

The core risk: **GPLv3's strong-copyleft provisions** (Section 5 & Section 11) dictate that any derivative work conveyed "to others" must be licensed as a whole under "this License" — i.e., any code that links to, derives from, or is otherwise tightly integrated with LibreCast Studio's GPLv3 code **cannot be distributed under a proprietary license without releasing the accompanying source code.**

This ADR formally defines the **commercial-derivative boundary** and establishes the architectural and procedural rules that prevent the LibreCast Studio fork from contaminating or being contaminated by proprietary Nexus code.

---

## 2. Definitions

| Term | Meaning |
|------|---------|
| **LibreCast Studio (the Fork)** | The `nova-obs-fork` repository, all submodules, and all code committed to any branch under `nova-obs-fork/` or its worktrees. |
| **Nexus Commercial Code** | Any proprietary code in the `nexusio-suite`, `nexus-studio`, `hybrid-dsp-engine`, or any other Nexus-owned repository, regardless of license. |
| **Derivative Work (DW)** | Any new or modified work (in source or binary form) that is based on, links to, or is combined with LibreCast Studio code. |
| **Convey** | Distribution or disclosure of source or binary to any third party (including internal distribution between business entities under common control, per FSF guidance on "effective technological measures"). |

---

## 3. Decision

### 3.1. **Strict No-Merge Boundary**

**A. No Proprietary-to-GPL — LibreCast Studio source tree MUST NOT receive contributions from or via the Nexus commercial codebase.**

This means:
- ❌ **No copying** of proprietary Nexus algorithms, DSP routines, UI components, or plugin logic into `nova-obs-fork/`.
- ❌ **No merging** of feature branches or commits from `nexusio-suite` or `nexus-studio` into any LibreCast Studio branch.
- ❌ **No vendoring** of proprietary `.dll`, `.so`, `.a`, or other binary artifacts owned by Nexus into the LibreCast Studio tree.
- ❌ **No dual-licensing** of LibreCast Studio code for commercial reuse without the explicit written consent of all copyright holders in the fork (the original StreamFX/Xaymar rights holder and any contributors).

**B. No GPL-to-Proprietary — Nexus commercial projects MUST NOT incorporate LibreCast Studio source.**

This means:
- ❌ **No `#include`** of LibreCast Studio headers into Nexus commercial source.
- ❌ **No linking** (static or dynamic) of LibreCast Studio object files or libraries into proprietary Nexus binaries.
- ❌ **No use** of LibreCast Studio as a build dependency (`add_subdirectory`, `FetchContent`, etc.) in any Nexus commercial CMake build.
- ❌ **No copying** of LibreCast Studio UI text, branding, or configuration strings into commercial products without a separate license.

**C. Violation Consequence**

Any breach of 3.1(A) or 3.1(B) is a **Tier-1 governance violation** requiring:
1. Immediate code removal and audit trail.
2. Notification to the LibreCast Studio maintainers and the Nexus legal/compliance team.
3. Mandatory post-incident review by the Chief of Staff and CFO before any further code can be committed.

### 3.2. **Clean-Room Interface Exception (for Interoperability Only)**

If a Nexus commercial product must use or interact with LibreCast Studio functionality **at the boundary only**, the following rules apply:

- ✅ The interaction MUST be through a **published, documented API** (e.g., OBS WebSocket, libobs plugin API, D-Bus, named pipes, or shared memory with documented schema).
- ✅ The Nexus commercial component MUST be a **separate process** (not linked into the same binary as LibreCast Studio).
- ✅ The Nexus commercial component MUST NOT copy or reproduce any LibreCast Studio source code, even to "call" the API. Reverse engineering for interoperability under 17 U.S.C. § 1201(f) or equivalent is tolerated, but clean-room reimplementation is preferred and documented.
- ✅ The communication boundary MUST NOT convey LibreCast Studio source or object code to the commercial side. Source must be inspected only at arm's length by a different team under a documented clean-room log.

**Implementation example:** A Nexus commercial tool communicates with LibreCast Studio via the `obs-websocket` protocol over TCP — this is permitted. A Nexus commercial plugin that `#include`s `source/obs/obs-source.hpp` from the fork — this is **not permitted.**

---

## 4. Enforcement Mechanisms

### 4.1. CI Gate (Automated)

The `license-check` job in `.github/workflows/validate.yml` enforces:
- Root `LICENSE` contains FSF GPLv3 text.
- All source files contain `SPDX-License-Identifier: GPL-3.0-or-later`.
- No prohibited dependencies are introduced.

**New requirement (effective immediately):** A `git diff` scan for cross-repository file content is added to the `license-check` job to detect any file content duplicated from the `nexusio-suite` or `nexus-studio` trees. Tooling: SHA-256 hash allowlist of approved file fingerprints; any hash not in the allowlist AND present in a Nexus commercial repo is flagged.

### 4.2. Pre-Merge Checklist (Manual)

All PRs to `nova-obs-fork` must pass:
- [ ] No file content matches any file in `nexusio-suite` or `nexus-studio` (checked via CI hash scan).
- [ ] No submodule URL points to a Nexus-owned proprietary repo.
- [ ] Author confirms: "I certify that no proprietary Nexus source code was copied, merged, or vendored into this PR." — sign-off on PR description.

### 4.3. Annual Audit

The Nexus Chief of Staff will conduct an annual audit of both repositories to confirm:
- No shared commit hashes between `nova-obs-fork` and commercial repos.
- No shared source file content (beyond public domain/MIT snippets ≤ 20 lines).
- No shared copyright headers or author lists.

---

## 5. Consequences

- **Community Trust:** LibreCast Studio remains a pure open-source project, eligible for community contributions and upstream OBS collaboration.
- **Legal Safety:** Mitigates the risk of GPL viral-copyleft affecting the proprietary Nexus portfolio.
- **Development Friction:** Requires a clean-room boundary for any Nexus-Studio ↔ LibreCast Studio integration work. This is an acceptable cost of the dual-licensing model.
- **Future Optionality:** If Nexus later decides to open-source a commercial component, it can be contributed to `nova-obs-fork` as a clean, separately-authored PR — not a merge of proprietary history.

---

## 6. References

- GNU GPL v3 full text: `/LICENSE`
- FSF interpretation of "Effective Technological Measures": https://www.gnu.org/licenses/gpl-faq.en.html#opportunistic
- License Audit: `docs/LICENSE_AUDIT.md`
- License Check Gate: `LICENSE-CHECK.md`
- Related ADR: none previous

---

## 7. Decision Log

| Date | Action | Author |
|------|--------|--------|
| 2026-08-30 | ADR created, accepted | Nexus Orchestrator |
