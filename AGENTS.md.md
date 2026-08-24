# AGENT ASSIGNMENT — OBS Fork / StreamFX

**Task ID:** t_e5f6a7b8
**Priority:** P0 (BLOCKER)
**Agent:** Vantage (Compliance & Strategy)
**Project:** obs-fork (StreamFX OBS plugin, branch `root`)
**Repo:** `C:/Users/bhogl/Projects/nexus-projects/nova-obs-fork` (.worktrees/t_e5f6a7b8)

## Task: License Transition — Enforce GPLv3-or-later (GPLv3+)

### Owner Directive
The owner has decided: **the fork's governing license is GPLv3-or-later (GPLv3+)**. Execute the transition; do not re-litigate the choice.

### Problem
`LICENSE` file = **GNU GPL v2** (June 1991) — stale and contradicts the owner's GPLv3+ decision.
`README.adoc` §Licenses claims **GPLv3 (or later)** and lists GPL-2.0 (obs-studio), (L)GPL-3.0 (Qt), MIT (nlohmann, glad, NVIDIA SDKs).
The contradiction must be resolved in favor of GPLv3+ to unblock Nexus ecosystem planning.

### Acceptance Criteria
1. Replace `LICENSE` with the canonical **GPLv3** text (FSF June 2007) and ensure the "or later" clause is present (GPLv3-or-later). Document the governing license as GPLv3+ in `docs/LICENSE_AUDIT.md`.
2. Produce a sub-component license matrix (StreamFX core, obs-studio dep, Qt, NVIDIA SDKs, nlohmann-json, glad) — flag any GPL/prop incompatibility with Nexus commercial clean-room goals.
3. Reconcile README §Licenses to match the actual `LICENSE` file verbatim.
4. Flag any source file whose header copyright vs. repo LICENSE is inconsistent.

### Hard Constraints
- Execute the transition: replacing `LICENSE` with GPLv3+ text is explicitly in scope (owner-authorized). No other upstream source rewrites unless a header fix is required by GPLv3+ adoption.
- Surface the commercial-derivative blocker clearly (GPL is copyleft; Nexus commercial tree is proprietary) — note GPLv3+ remains incompatible with a proprietary Nexus tree.
- Do not push without explicit authorization.
