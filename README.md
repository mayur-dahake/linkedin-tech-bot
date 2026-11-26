# linkedin-tech-bot

Automated **30 Days, 30 Hidden Concepts** LinkedIn & Dev.to engineering series across **`.NET`**, **`Angular`**, and **`SQL Server`** (90 structured concepts in Cycle 1, followed by Live Market Radar in Cycle 2+) with a GitHub Issue review flow, Pillow-generated 4:5 Before/After visual cards, and multi-slide LinkedIn PDF document carousels.

## Repository Structure

```text
linkedin-tech-bot/
├── .github/
│   └── workflows/
│       ├── daily_draft_review.yml    # Generates post, post_card.png & post_carousel.pdf; opens review issue
│       └── publish_on_approval.yml   # Publishes to LinkedIn & Dev.to on /publish or /publish carousel
├── gallery.html                      # Interactive local web gallery for all 90 days with live card mockups
├── linkedin_daily_bot.py             # Main Python bot script (Pillow generator, LinkedIn & Dev.to publisher)
├── thirty_days_curriculum.json       # 30 modern hidden concepts each for dotnet, angular, sql_server
├── series_state.json                 # Active tracker ({"track": "dotnet", "day": 1, "cycle": 1})
├── post_history.json                 # Published topic history to prevent duplicates in Cycle 2+
└── requirements.txt                  # Python dependencies (requests, pillow)
```

## How It Works

1. **Generate Daily Draft (`daily_draft_review.yml`)**
   - Runs daily targeting ~5:30 PM IST (using off-peak odd-minute GitHub schedule `11:47 UTC` / `5:17 PM IST` with a `12:07 UTC` fallback) or manually via `workflow_dispatch` (with optional `track` and `day` overrides).
   - Reads the active `track`, `day`, and `cycle` from `series_state.json`, queries Gemini for a Before/After code comparison + minimal commentary, renders a 4:5 (`1080×1350`) visual card (`post_card.png`) and a 4-slide PDF carousel (`post_carousel.pdf`) with `@maayurdahake` branding.
   - Pushes preview images and PDF to an isolated `previews` branch, closes any stale open `📝 Review Draft:` issues, and opens today's review issue assigned to the repo owner.
2. **Publish or Regenerate (`publish_on_approval.yml`)**
   - Edit the issue body directly in GitHub if you want to tweak wording before publishing.
   - Comment **`/publish`** to publish the single visual card to LinkedIn & Dev.to.
   - Comment **`/publish carousel`** to publish the 4-slide PDF carousel document to LinkedIn (`/rest/documents`) & Dev.to.
   - Comment **`/regenerate`** to generate a fresh draft, card, and carousel.
   - Advances `series_state.json`, records the topic in `post_history.json`, commits the updated state back to `main`, and closes the issue.

## Interactive Local Gallery (`gallery.html`)

Open [`gallery.html`](file:///Volumes/SSD/Projects/linkedin-tech-bot/gallery.html) directly in any web browser (`open gallery.html`):
- **All 90 Days:** Browse all 30 days of .NET & C#, 30 days of Angular, and 30 days of SQL Server.
- **Track & Day Matrix:** Instant day slider, track switcher, and fast topic search filter.
- **Visual Card Mockup:** Accurate 4:5 live CSS rendering matching Pillow's unslopped card layout.
- **4-Slide Carousel Viewer:** Interactive slide preview (`Hook ➔ Before ➔ After ➔ Takeaways`).
- **One-Click Copy:** Instant copy of LinkedIn formatted commentary and terminal CLI command.

## GitHub Secrets & Variables

Configure under **Settings → Secrets and variables → Actions**:

### Required Secrets
- `GEMINI_API_KEY`: Google Gemini API key used by `generate`.
- `LINKEDIN_ACCESS_TOKEN`: LinkedIn OAuth 2.0 token with `w_member_social` (personal) or `w_organization_social` (company page) permission.
- `LINKEDIN_AUTHOR_URN`: `urn:li:person:<id>` or `urn:li:organization:<id>`.

### Optional Secrets & Variables
- `DEVTO_API_KEY`: Dev.to API key (`dev.to/settings/extensions`) for automatic cross-posting.
- `GEMINI_MODEL`: Gemini model name (defaults to `gemini-3.8-flash`, falling back to `gemini-3.5-flash-lite`).
- `LINKEDIN_API_VERSION`: `YYYYMM` header for LinkedIn REST APIs (defaults to `202610`).

## Local Setup & CLI Usage

```bash
pip install -r requirements.txt

# Generate draft_content.json, post_card.png and post_carousel.pdf
export GEMINI_API_KEY="your-key"
python3 linkedin_daily_bot.py generate --track dotnet --day 1 --carousel

# Publish single card to LinkedIn (and Dev.to if DEVTO_API_KEY is set)
export LINKEDIN_ACCESS_TOKEN="your-token"
export LINKEDIN_AUTHOR_URN="urn:li:person:your-id"
python3 linkedin_daily_bot.py publish --text-file approved_text.txt --image post_card.png

# Or publish 4-slide PDF carousel document to LinkedIn
python3 linkedin_daily_bot.py publish --text-file approved_text.txt --carousel --document post_carousel.pdf
```
