# Project Roadmap — linkedin-tech-bot

## Phase 1: Core Automation (Completed)
- [x] **90-Day Structured Curriculum:** 30 hidden concepts each for `.NET / C#`, `Angular`, and `SQL Server` (`thirty_days_curriculum.json`).
- [x] **Cycle 2+ Live Market Radar:** Gemini `google_search` grounding with `post_history.json` deduplication.
- [x] **4:5 Before/After Visual Card:** Gradient-Glass Pillow renderer (`1080×1350`) with syntax highlighting, 3 metric boxes, and `@maayurdahake` footer (`linkedin_daily_bot.py`).
- [x] **Minimal LinkedIn Formatting:** Unicode Sans-Serif bold headers/anchors with inline code stripping so the image carries the code.
- [x] **Human-in-the-Loop GitHub Workflow:** Daily `4:00 PM IST` (`10:30 UTC`) draft generation, `previews` branch isolation, auto-assignment notifications, `/regenerate`, `/publish`, and `503` API retry handling (`.github/workflows/`).
- [x] **Cross-Posting:** Automated publishing to **LinkedIn** and **Dev.to** (with uncropped card embed + `main_image`).

---

## Phase 2: Reliability & Content Quality
- [ ] **Guaranteed 4:00 PM IST Cron Fallback**
  - Add a free [cron-job.org](https://cron-job.org/) `workflow_dispatch` trigger alongside GitHub's `schedule`.
  - Add a same-day duplicate guard in `daily_draft_review.yml` so double-triggers never open duplicate issues.
- [ ] **60-Day LinkedIn Token Expiry Warning**
  - Store `LINKEDIN_TOKEN_UPDATED_AT` as a GitHub repository variable.
  - Inject a countdown reminder banner into the daily review issue starting at Day 50 to prevent surprise `401 Unauthorized` errors.
- [ ] **Dedicated Dev.to Long-Form Copy (`devto_markdown`)**
  - Generate a separate `devto_markdown` field (~200 words with copyable `Before`/`After` Markdown code blocks) while keeping LinkedIn commentary ultra-minimal (<90 words).
- [ ] **Card Overflow & Code Sanity Guardrail**
  - Validate `bad_code` and `good_code` line counts and character widths in `linkedin_daily_bot.py` before rendering, auto-shrinking font size or re-prompting Gemini if lines would clip.

---

## Phase 3: Growth & Rich Formats
- [ ] **Optional Carousel Mode (`--carousel`)**
  - Render 3–4 linked `4:5` slides (Hook → Before/After → Gotcha → Takeaway) and export a LinkedIn-ready PDF document for deeper SQL/Angular topics.
- [ ] **Automated Series Index (`SERIES_INDEX.md`)**
  - Auto-update a browsable index linking every published day by track (`dotnet`, `angular`, `sql_server`) with its Dev.to URL.
- [ ] **Dev.to Series Tagging**
  - Group articles into official Dev.to series (`"30 Days of Hidden .NET Gems"`, etc.) so readers can navigate between days directly on Dev.to.
