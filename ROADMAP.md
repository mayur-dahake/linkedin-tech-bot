# Project Roadmap — linkedin-tech-bot

## Phase 1: Core Automation (Completed)
- [x] **90-Day Structured Curriculum:** 30 hidden concepts each for `.NET / C#`, `Angular`, and `SQL Server` (`thirty_days_curriculum.json`).
- [x] **Cycle 2+ Live Market Radar:** Gemini `google_search` grounding with `post_history.json` deduplication.
- [x] **4:5 Before/After Visual Card:** Gradient-Glass Pillow renderer (`1080×1350`) with syntax highlighting, 3 metric boxes, and `@maayurdahake` footer (`linkedin_daily_bot.py`).
- [x] **Minimal LinkedIn Formatting:** Unicode Sans-Serif bold headers/anchors with inline code stripping so the image carries the code.
- [x] **Human-in-the-Loop GitHub Workflow:** Daily `4:00 PM IST` (`10:30 UTC`) draft generation, `previews` branch isolation, auto-assignment notifications, `/regenerate`, `/publish`, and `503` API retry handling (`.github/workflows/`).
- [x] **Cross-Posting:** Automated publishing to **LinkedIn** and **Dev.to** (with uncropped card embed + `main_image`).

---

## Phase 2: Reliability & Content Quality (Completed)
- [x] **Guaranteed 4:00 PM IST Cron Fallback & Duplicate Guard**
  - Added same-day duplicate guard (`force` input override) in `daily_draft_review.yml` so pairing GitHub's `schedule` with an external [cron-job.org](https://cron-job.org/) `workflow_dispatch` trigger never opens duplicate issues.
- [x] **60-Day LinkedIn Token Expiry Warning**
  - Reads `LINKEDIN_TOKEN_UPDATED_AT` (`YYYY-MM-DD` repository variable) and injects an alert banner into the daily review issue starting at Day 50 (`<= 10` days remaining).
- [x] **Dedicated Dev.to Long-Form Copy & Series Grouping**
  - Keeps LinkedIn commentary minimal (<90 words, no inline code), while `_compose_devto_markdown()` automatically injects copyable `### Before` and `### After` fenced code blocks, the uncropped 4:5 card, and official Dev.to `series` grouping (`"30 Days of Hidden .NET & C# Gems"`, etc.).
- [x] **Card Overflow & Code Sanity Guardrail**
  - Dynamically scales code font size (`19px` → `17px` → `15px`) and wrapping width (`52` → `58` → `64` chars) in `create_visual_card()` so longer snippets never clip inside the `BEFORE` and `AFTER` glass panels.

---

## Phase 3: Growth & Rich Formats (Next)
- [ ] **Optional Carousel Mode (`--carousel`)**
  - Render 3–4 linked `4:5` slides (Hook → Before/After → Gotcha → Takeaway) and export a LinkedIn-ready PDF document for deeper SQL/Angular topics.
- [ ] **Automated Series Index (`SERIES_INDEX.md`)**
  - Auto-update a browsable index linking every published day by track (`dotnet`, `angular`, `sql_server`) with its Dev.to URL.
