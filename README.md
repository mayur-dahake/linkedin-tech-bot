# linkedin-tech-bot

Automated **30 Days, 30 Hidden Concepts** LinkedIn & Dev.to engineering series across **`.NET`**, **`Angular`**, and **`SQL Server`** (90 structured concepts in Cycle 1, followed by Live Market Radar in Cycle 2+) with a GitHub Issue review flow and Pillow-generated 4:5 Before/After visual cards.

## Repository Structure

```text
linkedin-tech-bot/
├── .github/
│   └── workflows/
│       ├── daily_draft_review.yml    # Generates post + post_card.png & opens review issue
│       └── publish_on_approval.yml   # Publishes to LinkedIn & Dev.to on /publish (or /regenerate)
├── linkedin_daily_bot.py             # Main Python bot script
├── thirty_days_curriculum.json       # 30 hidden concepts each for dotnet, angular, sql_server
├── series_state.json                 # Active tracker ({"track": "dotnet", "day": 1, "cycle": 1})
├── post_history.json                 # Published topic history to prevent duplicates in Cycle 2+
└── requirements.txt                  # Python dependencies (requests, pillow)
```

## How It Works

1. **Generate Daily Draft (`daily_draft_review.yml`)**
   - Runs daily at `10:30 UTC` (`16:00 IST` / `4:00 PM IST`) or manually via `workflow_dispatch` (with optional `track` and `day` overrides).
   - Reads the active `track`, `day`, and `cycle` from `series_state.json`, queries Gemini for a Before/After code comparison + minimal commentary, and renders a 4:5 (`1080×1350`) Gradient-Glass card (`post_card.png`) with `@maayurdahake` branding.
   - Pushes preview images to an isolated `previews` branch, closes any stale open `📝 Review Draft:` issues, and opens today's review issue assigned to the repo owner.
2. **Publish or Regenerate (`publish_on_approval.yml`)**
   - Edit the issue body directly in GitHub if you want to tweak wording before publishing.
   - Comment **`/regenerate`** to generate a fresh draft and card, or **`/publish`** (or `/approve`) to publish (restricted to repo `OWNER`, `MEMBER`, or `COLLABORATOR`).
   - Publishes the card and Unicode-formatted minimal commentary to **LinkedIn** (`/rest/images` + `/rest/posts`) and, when configured, cross-posts the full Markdown + uncropped card to **Dev.to**.
   - Advances `series_state.json`, records the topic in `post_history.json`, commits the updated state back to `main`, and closes the issue.

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

# Generate draft_content.json and post_card.png (uses series_state.json unless overridden)
export GEMINI_API_KEY="your-key"
python3 linkedin_daily_bot.py generate --track dotnet --day 1

# Publish to LinkedIn (and Dev.to if DEVTO_API_KEY is set)
export LINKEDIN_ACCESS_TOKEN="your-token"
export LINKEDIN_AUTHOR_URN="urn:li:person:your-id"
python3 linkedin_daily_bot.py publish --text-file approved_text.txt --image post_card.png
```
