# linkedin-tech-bot

Automated **30 Days, 30 Hidden Concepts** LinkedIn series across **`.NET`**, **`Angular`**, and **`SQL Server`** (90 concepts total) with a GitHub Issue review flow and Pillow-generated visual comparison cards.

## Repository Structure

```text
linkedin-tech-bot/
├── .github/
│   └── workflows/
│       ├── daily_draft_review.yml    # Generates post + post_card.png & opens review issue
│       └── publish_on_approval.yml   # Publishes to LinkedIn when you comment /publish or /approve
├── linkedin_daily_bot.py             # Main Python bot script
├── thirty_days_curriculum.json       # 30 hidden concepts each for dotnet, angular, sql_server
├── series_state.json                 # Active tracker ({"track": "dotnet", "day": 1})
└── requirements.txt                  # Python dependencies (requests, pillow)
```

## How It Works

1. **Generate Daily Draft (`daily_draft_review.yml`)**
   - Runs daily at `12:00 UTC` (`17:30 IST` / `07:00 EST`) or manually via `workflow_dispatch` (with optional `track`, `day`, and `force` inputs).
   - Reads the active `track` and `day` from `series_state.json`, queries Gemini for a bad-vs-good code comparison + anchored metric bullets, writes `draft_content.json`, and renders `post_card.png`.
   - Uploads `post_card.png` as the `post-card` artifact and opens a GitHub Issue (`📝 Review Draft: ...`), skipping duplicates if an open draft with the same title already exists.
2. **Publish on Approval (`publish_on_approval.yml`)**
   - Edit the issue body directly in GitHub if you want to tweak the wording before publishing.
   - Comment `/publish` or `/approve` on the open review issue (restricted to repo `OWNER`, `MEMBER`, or `COLLABORATOR`).
   - Downloads the `post-card` artifact, extracts the approved text between the `---` dividers, uploads `post_card.png` via LinkedIn's `/rest/images` API, publishes via `/rest/posts`, advances `series_state.json`, commits the updated state back to the default branch, and closes the issue.

## GitHub Secrets & Variables

Configure under **Settings -> Secrets and variables -> Actions**:

### Required Secrets
- `GEMINI_API_KEY`: Google Gemini API key used by `generate`.
- `LINKEDIN_ACCESS_TOKEN`: LinkedIn OAuth 2.0 token with `w_member_social` (personal) or `w_organization_social` (company page) permission.
- `LINKEDIN_AUTHOR_URN`: `urn:li:person:<id>` or `urn:li:organization:<id>`.

### Optional Repository Variables
- `GEMINI_MODEL`: Gemini model name (defaults to `gemini-2.5-flash`).
- `LINKEDIN_API_VERSION`: `YYYYMM` header for LinkedIn REST APIs (defaults to `202610`).

## Local Setup & CLI Usage

```bash
pip install -r requirements.txt

# Generate draft_content.json and post_card.png (uses series_state.json unless overridden)
export GEMINI_API_KEY="your-key"
python3 linkedin_daily_bot.py generate --track dotnet --day 1

# Publish to LinkedIn
export LINKEDIN_ACCESS_TOKEN="your-token"
export LINKEDIN_AUTHOR_URN="urn:li:person:your-id"
python3 linkedin_daily_bot.py publish --text-file approved_text.txt --image post_card.png
```
