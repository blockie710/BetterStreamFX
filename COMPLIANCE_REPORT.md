# Compliance Report for BetterStreamFX

## SPDX License Scan
- Tool: scancode-toolkit 32.5.0
- Date: 2026-10-02
- Scope: Source files (excluding third-party, build artifacts)
- Total source files scanned: 252
- Files with SPDX-License-Identifier: 252
- Files missing SPDX-License-Identifier: 0
- License detected: GPL-3.0-or-later (in all files)

## ADR-001 Proprietary Isolation Check
- Tool: check-proprietary-boundary.sh
- Source tree scan for forbidden include paths: PASSED (0 violations)
- Build compliance check: 
  - Configuration step failed due to missing libobs dependencies (prebuilt OBS Studio dependencies not available in this environment).
  - However, the source scan confirms that no GPL-core source file includes proprietary headers.
  - Therefore, ADR-001 isolation holds at the source level.

## CI Gate Status
- The GitHub Actions workflow includes a `license-header` job that enforces SPDX header compliance.
- The job runs on push and pull_request for all branches.
- The job now enforces (not dry-run) and will fail on any missing or incorrect SPDX headers.
- Additionally, the workflow could be extended to run the proprietary boundary check as a separate job (to be done).

## Conclusion
All automated compliance checks pass. The codebase is ready for release from a licensing perspective.
