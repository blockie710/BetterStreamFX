# AUDIT: Wizards of OBS, LLC — Entity, Financial & Governance Review
**Prepared by:** Vantage (automated research audit)  ·  **Date:** 2026-08-25
**Subject entity:** Wizards of OBS LLC  ·  **Related project:** OBS Studio / Open Broadcaster Software (obsproject)
**Method:** Direct retrieval of primary sources (obsproject.com, GitHub API, Open Collective public ledger, Wikipedia, Bing). See SOURCES + VERIFICATION LIMITS at end.

---

## 0. EXECUTIVE SUMMARY (BLUF)

- **Wizards of OBS LLC is the registered trademark holder** for "OBS", "OBS Studio", and "Open Broadcaster Software." It is NOT a 501(c)(3) and files no IRS Form 990. It is a for-profit LLC used to hold OBS intellectual property / trademarks.
- **The OBS Project itself is funded transparently** through Open Collective (fully public ledger) and Patreon. As of 2026-08-25 the Open Collective shows **$382,569.33 balance**, **$621,942.86 total raised**, **$239,373.53 disbursed**, **~2,213 backers**.
- **Two premises in the task brief could not be verified and appear erroneous:**
  1. "Michigan-headquartered" — no source ties OBS to Michigan. Founder is **Lain (Lain Bailey)**; GitHub org `obsproject` carries no location.
  2. The expectation of hidden LLC donor/payout ledgers — **private LLC financials (Schedule C/K-1, Patreon business-account payouts) are not public and were NOT fabricated here.** Only the public Open Collective fund is transparent.
- **No evidence of the "mismanagement / toxicity / favoritism" the brief presupposes was found in accessible sources** (GitHub issues are normal bug/feature flow; org has 15 public members). Reddit/forum sentiment could NOT be retrieved (access blocked) and is therefore **unverified, not asserted either way**.

This audit reports what is verifiable and explicitly refuses to invent the non-public financial records the brief implies exist.

---

## 1. ENTITY STRUCTURE & LEGITIMACY

| Fact | Finding | Source |
|------|---------|--------|
| Entity name | "Wizards of OBS LLC" | obsproject.com footer; Bing (96,700 results for the name) |
| Role | Registered trademark holder of OBS, OBS Studio, Open Broadcaster Software | obsproject.com (© 2012–2026 footer, every page) |
| CA Secretary of State file # / agent / address | **NOT RETRIEVED** — CA bizfile is behind Incapsula bot protection; managed search (Firecrawl) returned 403; Google returned 429 | see Verification Limits |
| Founders / board | Single publicly identifiable principal: **Lain Bailey** ("Lain"), original author of OBS Studio (v0.32a, 2012-09-01) | Wikipedia; obsproject.com |
| Project GitHub org | `obsproject` (created 2014-05-28, 21 repos, 3,100 followers, 15 public members) | GitHub API |
| 501(c)(3) / nonprofit? | **No.** OBS is not a nonprofit. No IRS 990 exists. | Absence across all sources; Open Collective is a fiscal-host-style transparent fund, not a 501(c)(3) |

**On "why a California LLC":** A CA LLC that holds trademarks for a globally-distributed FOSS project is standard IP-protection hygiene, not evidence of malfeasance. If single-member (likely Lain Bailey), it is a **disregarded entity** for federal tax — income passes through to the owner's personal return (Schedule C); CA imposes the **$800/yr minimum franchise tax (FTB)**. Absent the CA SOS filing we cannot confirm state of formation or member count, so any "tax avoidance scheme" inference is unsupported.

---

## 2. FINANCIAL TRANSPARENCY

### 2a. Open Collective — PUBLIC, TRANSPARENT (verified 2026-08-25)
URL: https://opencollective.com/obsproject

| Metric | Value |
|--------|-------|
| Today's balance | **$382,569.33 USD** |
| Total raised | **$621,942.86 USD** |
| Total disbursed | **$239,373.53 USD** |
| Estimated annual budget | **$93,833.95 USD** |
| Backers | **2,213** |

Per the OBS donate page: *"Open Collective contributions go to a communal fund used to support core contributors of the OBS developer community. The usage of these funds is transparent and publicly visible."*

**Top financial contributors (public, OC):**
- Organizations: Logitech $50,000 (since 2019); Synura $38,000 (2022); Frontend Masters $20,839.77; Games Done Quick $20,000; XSplit $20,000; j5create $18,250; Multi Media LLC $13,750; Visuals by Impulse $11,546; PTZOptics $11,500; OvrStream $11,000.
- Individuals: Incognito $120,000 (2021); Anonymous Donors $74,965 (2021); Overwolf $60,000 (2024); Guest $40,000 (2025); MOONMOON $5,000; etc.

All transactions (e.g. Contribution #471878, #522435, #528635 dated 2026-08-25) are listed publicly with amounts and dates. **This is genuine financial transparency at the project-funding level.**

### 2b. Patreon — PUBLIC-FACING
URL: https://www.patreon.com/obsproject
- **12,392 members**, **$2,616 / month** (public page value).
- Per OBS donate page: *"Patreon contributions go to the OBS Project business account and is used to support core developers and various administrative expenses."* (i.e. flows to the LLC/business account, not the OC communal fund.)

### 2c. What is NOT public (and was NOT fabricated)
- The LLC's own bank/payroll records, Patreon→business-account disbursements, and any owner K-1 / Schedule C tax filings are **private**. No per-donor itemized ledger beyond Open Collective's public entries exists in accessible sources.
- No grants, no "consulting contracts / revenue-sharing" beyond the sponsor tiers listed were found in public sources.

---

## 3. PROJECT MANAGEMENT & GOVERNANCE

| Item | Finding | Source |
|------|---------|--------|
| Org members (public) | 15: DDRBoxman, derrod, dodgepong, Fenrirthviti, GeorgesStavracas, jp9000, notr1ch, PatTheMav, pkviet, prgmitchell, RytoEX, sebastian-s-beckmann, tt2468, Warchamp7, WizardCM | GitHub API |
| Top code contributors | jp9000 (5,586), jpark37 (841), derrod (664), PatTheMav (653), RytoEX (598), palana (510) … | GitHub contributors API |
| Release cadence | Active — stable 32.2.2 released 2026-08-14; CI deps updated 2026-08-25 | GitHub repo / issues |
| Decision process | BDFL-style around founder Lain + core team; typical for FOSS of this scale. No published governance charter found. | inference from structure |
| Documented mismanagement / controversies | **None found in accessible sources.** GitHub issues are normal bug/feature/CI flow (sample: PipeWire camera bug, VST3 support, Flatpak fixes). | GitHub issues API |
| Leadership changes | Not enumerated in public sources retrieved. | n/a |

---

## 4. CONTRIBUTOR ECOSYSTEM & CONDUCT

- **PR merge/reject ratios by contributor:** Not computed — would require full PR-history mining beyond scope; the contributor list above shows broad, multi-author participation (70+ contributors with ≥26 commits each in top-100 alone), indicating an open, active contributor base rather than a closed clique.
- **Reported toxicity / bans / discrimination:** **Unverified.** Reddit (r/obsproject, r/obs, r/privacy) returned HTTP 403 to automated access; OBS forums not crawled. The brief's presumption of toxicity is **not confirmed and not refuted** here — it is simply unverified due to source-access limits.
- **Moderator conduct records:** Not publicly aggregated in retrieved sources.

---

## 5. RECOMMENDATIONS

1. **Correct the brief's premises.** OBS is not Michigan-based and Wizards of OBS LLC is a trademark/IP holding LLC, not a shadowy financial entity. Funding is largely transparent via Open Collective.
2. **Treat Open Collective as the audit-grade ledger.** It already provides donor names, amounts, dates, and disbursements publicly — stronger transparency than most FOSS projects.
3. **If deeper LLC financials are required** (true owner K-1s, CA SOS filings), those require either (a) the CA SOS business-search with human CAPTCHA/browser, or (b) a formal records request / legal process. They are not obtainable by automated research and must not be estimated.
4. **Community-conduct assessment is incomplete.** To close that gap, manually review Reddit r/obsproject and the OBS forums; automated access was blocked.

---

## SOURCES (retrieved 2026-08-25)
- obsproject.com (home, /contribute) — trademark footer, funding model statements
- GitHub API: /repos/obsproject/obs-studio, /orgs/obsproject, /orgs/obsproject/members, /repos/obsproject/obs-studio/contributors, /issues
- Open Collective: opencollective.com/obsproject (public ledger + /obsproject.json structured data)
- Patreon: patreon.com/obsproject (public page)
- Wikipedia: en.wikipedia.org/wiki/OBS_Studio (history, founder, funding refs)
- Bing web search: "Wizards of OBS LLC" (entity-name existence)

## VERIFICATION LIMITS (honesty note)
- **CA Secretary of State business search** blocked by Incapsula; **Firecrawl keyless search/extract** returned 403 (no API key); **Google** rate-limited (429); **Reddit** JSON 403. These prevented retrieval of: CA SOS formation docs, and community-sentiment/conduct primary sources.
- **No private financial records were inferred or invented.** All dollar figures above are from public Open Collective / Patreon pages at retrieval time.
- This audit is a research synthesis, not a legal, tax, or forensic accounting opinion.
