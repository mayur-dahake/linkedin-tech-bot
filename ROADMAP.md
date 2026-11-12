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
  - Keeps LinkedIn commentary minimal (<90 words, no inline code), while generating `devto_markdown` (~180–220 words with copyable `### Before` / `### After` fenced code blocks), uncropped 4:5 card, and official Dev.to `series` grouping.
- [x] **Card Overflow & Code Sanity Guardrail**
  - Dynamically scales code font size (`19px` → `17px` → `15px`) and wrapping width (`52` → `58` → `64` chars) in `create_visual_card()` so longer snippets never clip inside the `BEFORE` and `AFTER` glass panels.

---

## Phase 3: Growth & Rich Formats (Completed)
- [x] **Optional Carousel Mode (`--carousel`)**
  - Renders 4 linked `4:5` slides (Hook + Metrics → Before → After → Takeaways) and exports `post_carousel.pdf` via Pillow, with a `carousel` boolean input in `daily_draft_review.yml` that uploads the PDF artifact.
- [x] **Automated Series Index (`SERIES_INDEX.md`)**
  - Automatically maintains `SERIES_INDEX.md` grouped by track (`dotnet`, `angular`, `sql_server`) with each published post's Dev.to article link and date, committed back to `main` on `/publish`.
