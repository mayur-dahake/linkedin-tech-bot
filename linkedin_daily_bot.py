"""
LinkedIn 30-Day Series Bot: Hidden & Underused Concepts
=======================================================
Covers 30 Days of Hidden Concepts for .NET, Angular, and SQL Server.
Automatically tracks "Day X of 30", generates visual code comparison cards,
and publishes to LinkedIn upon approval.

Enforces high-retention technical bullet pattern:
- **[Tech Anchor]:** [Exact metric, performance difference, or code trade-off]

Usage:
  python linkedin_daily_bot.py generate [--track dotnet|angular|sql_server] [--day N]
  python linkedin_daily_bot.py publish [--text "..." | --text-file FILE] [--image "..."]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

CURRICULUM_FILE = "thirty_days_curriculum.json"
STATE_FILE = "series_state.json"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash")
TRANSIENT_GEMINI_STATUS_CODES = (429, 500, 502, 503, 504)
MODEL_FALLBACK_STATUS_CODES = (400, 404, 429, 500, 502, 503, 504)
DEFAULT_LINKEDIN_API_VERSION = "202401"
MAX_LINKEDIN_POST_CHARS = 3000

_PRESERVED_LITTLE_TOKEN_RE = re.compile(
    r"@\[[^\]]+\]\(urn:li:[^)]+\)"
    r"|\{hashtag\|[^}]+\}"
    r"|(?:(?<=^)|(?<=\s))#[A-Za-z][A-Za-z0-9_]*"
)
_LITTLE_RESERVED_CHARS_RE = re.compile(r"([\\|{}@\[\]()<>#*_~])")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"track": "dotnet", "day": 1}


def save_state(state: dict) -> None:
    tmp_path = f"{STATE_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, STATE_FILE)


def get_current_item(track: str | None = None, day: int | None = None) -> tuple:
    state = load_state()
    active_track = track or state.get("track", "dotnet")
    active_day = day or state.get("day", 1)

    curriculum_path = Path(CURRICULUM_FILE)
    if not curriculum_path.exists():
        curriculum_path = Path("artifacts/file_generation/ttl=63d/output") / CURRICULUM_FILE

    with open(curriculum_path, "r", encoding="utf-8") as f:
        curriculum = json.load(f)

    track_items = curriculum.get(active_track, curriculum["dotnet"])
    idx = (active_day - 1) % len(track_items)
    item = track_items[idx]

    track_names = {
        "dotnet": ".NET & C#",
        "angular": "Angular",
        "sql_server": "SQL Server",
    }
    track_display = track_names.get(active_track, ".NET & C#")
    return active_track, item["day"], track_display, item


def _clean_post_for_linkedin(text: str) -> str:
    """Strip GitHub-only Markdown emphasis (**bold**) before Little Text escaping."""
    return re.sub(r"\*\*([^*\n]+?)\*\*", r"\1", text).strip()


def escape_linkedin_little_text(text: str) -> str:
    """Escape LinkedIn Little Text Format reserved chars while preserving hashtags & mentions."""
    chunks: list[str] = []
    cursor = 0
    for match in _PRESERVED_LITTLE_TOKEN_RE.finditer(text):
        if match.start() > cursor:
            plain = text[cursor : match.start()]
            chunks.append(_LITTLE_RESERVED_CHARS_RE.sub(r"\\\1", plain))
        chunks.append(match.group(0))
        cursor = match.end()
    if cursor < len(text):
        chunks.append(_LITTLE_RESERVED_CHARS_RE.sub(r"\\\1", text[cursor:]))
    return "".join(chunks)


def _raise_for_status_with_body(
    resp: requests.Response,
    label: str,
    secret: str = "",
) -> None:
    if resp.ok:
        return
    body = resp.text
    if secret:
        body = body.replace(secret, "***")
    print(f"{label} failed with HTTP {resp.status_code}: {body[:1000]}", file=sys.stderr)
    resp.raise_for_status()


def _post_gemini_generate(
    models_to_try: list[str],
    headers: dict[str, str],
    payload: dict,
    clean_key: str,
) -> requests.Response:
    """Posts to Gemini generateContent with backoff retries and model fallbacks."""
    retry_delays = (2.0, 5.0) if len(models_to_try) == 1 else (2.0,)

    for idx, model in enumerate(models_to_try):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        has_next_model = idx + 1 < len(models_to_try)

        for attempt in range(len(retry_delays) + 1):
            response: requests.Response | None = None
            last_exc: requests.RequestException | None = None
            retry_reason: str | None = None

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
            except requests.RequestException as exc:
                last_exc = exc
                retry_reason = f"request failed ({exc})"
            else:
                if response.ok:
                    return response

                err_text = response.text
                if "API_KEY_INVALID" in err_text or "API key not valid" in err_text:
                    print(
                        "Error: GEMINI_API_KEY was rejected by Google (API_KEY_INVALID). "
                        "Verify the key in Google AI Studio and update the GEMINI_API_KEY GitHub Secret.",
                        file=sys.stderr,
                    )
                    _raise_for_status_with_body(response, f"Gemini API ({model})", secret=clean_key)

                if response.status_code in TRANSIENT_GEMINI_STATUS_CODES:
                    retry_reason = f"returned HTTP {response.status_code}"
                elif has_next_model and response.status_code in MODEL_FALLBACK_STATUS_CODES:
                    print(
                        f"Warning: model '{model}' returned HTTP {response.status_code} "
                        f"({err_text[:200]}); trying next model...",
                        file=sys.stderr,
                    )
                    break
                else:
                    _raise_for_status_with_body(response, f"Gemini API ({model})", secret=clean_key)

            if attempt < len(retry_delays):
                delay = retry_delays[attempt]
                print(
                    f"Warning: model '{model}' {retry_reason}; retrying in {delay:.0f}s...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue

            if has_next_model:
                print(f"Warning: model '{model}' {retry_reason}; trying next model...", file=sys.stderr)
                break

            if response is not None:
                _raise_for_status_with_body(response, f"Gemini API ({model})", secret=clean_key)
            assert last_exc is not None
            raise last_exc

    raise RuntimeError("No Gemini models configured to handle generateContent request.")


def generate_visual_post_data(api_key: str, track: str | None = None, day: int | None = None) -> dict:
    """Calls Gemini API to generate structured visual code comparison data with anchored metric bullets."""
    active_track, day_num, track_display, item = get_current_item(track, day)
    configured_model = os.environ.get("GEMINI_MODEL", "").strip()
    models_to_try = [configured_model] if configured_model else list(FALLBACK_GEMINI_MODELS)
    clean_key = api_key.strip().strip('"').strip("'")

    system_prompt = f"""
You are an expert Fullstack Architect writing Day {day_num} of a 30-day LinkedIn series:
"🔥 30 Days, 30 Hidden Concepts in {track_display}".

Today's Topic: {item['concept']}
Guidance: {item['focus']}

Requirements:
- Focus on why this is a HIDDEN GEM: highly useful in production, but 90% of developers don't know it or use a slower/clunkier pattern.
- Provide a clear, concrete code comparison:
1. The Common / Clunky / Slower Pattern (bad_code)
  2. The Hidden / Performant Pattern (good_code)
- Be specific with exact syntax (C#, TypeScript, or T-SQL), keeping each code line <= 42 characters so it fits cleanly inside the card box.

MANDATORY POST COMMENTARY BULLET RULE:
Every single bullet point under the production impact section MUST strictly follow this exact syntax:
- **[Tech Anchor]:** [Exact metric, benchmark figure, or technical trade-off]

Examples of required bullet format:
- **Memory Allocation:** Zero heap allocation compared to 48 bytes allocated per substring in standard string slicing.
- **Hardware Vectorization:** Leverages SIMD instructions to evaluate 16-32 bytes concurrently in a single CPU cycle.
- **GC Pressure:** Eliminates Gen0 collections on high-throughput microservices handling 5,000+ req/sec.

Return STRICT JSON with these keys:
{{
  "series_badge": "🔥 DAY {day_num}/30 • HIDDEN {track_display.upper()} GEMS",
  "title": "{item['concept']}",
  "bad_label": "❌ COMMON / CLUNKY PATTERN",
  "bad_code": "2 to 4 lines of realistic code showing the everyday suboptimal pattern",
  "good_label": "✅ HIDDEN GEM / OPTIMIZED",
  "good_code": "2 to 4 lines of clean, modern, performant code",
  "key_metric": "A punchy impact line (e.g. '⚡ 10x Faster • Zero Allocations')",
  "post_text": "Complete ready-to-post LinkedIn text (under 2400 chars) structured as:\\n\\n🔥 Day {day_num} of 30: Hidden {track_display} Concepts\\n\\n[A punchy 2-line hook explaining what most developers get wrong]\\n\\n❌ Common Approach:\\n[formatted code]\\n\\n✅ Hidden Gem Approach:\\n[formatted code]\\n\\n⚡ Production Impact & Trade-offs:\\n• **[Tech Anchor 1]:** [Exact metric or trade-off]\\n• **[Tech Anchor 2]:** [Exact metric or trade-off]\\n• **[Tech Anchor 3]:** [Exact metric or trade-off]\\n\\nHave you leveraged this in your production apps?\\n\\n#DotNet #Angular #SQLServer #SoftwareEngineering #WebDevelopment"
}}
"""

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": clean_key,
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    response = _post_gemini_generate(models_to_try, headers, payload, clean_key)
    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()
    data = json.loads(raw_text)
    data["track"] = active_track
    data["day"] = day_num
    return data


def _load_font(size: int, mono: bool = False, bold: bool = False) -> ImageFont.ImageFont:
    if mono:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/System/Library/Fonts/Supplemental/Courier New.ttf",
            "/Library/Fonts/Courier New.ttf",
        ]
    elif bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_code_block(code: str, max_chars: int = 41, max_lines: int = 10) -> str:
    wrapped_lines: list[str] = []
    for raw_line in (code or "").splitlines():
        if not raw_line.strip():
            wrapped_lines.append("")
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        sub_indent = " " * min(indent + 2, 8)
        parts = textwrap.wrap(
            raw_line,
            width=max_chars,
            subsequent_indent=sub_indent,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped_lines.extend(parts or [""])
    return "\n".join(wrapped_lines[:max_lines])


def create_visual_card(data: dict, output_path: str = "post_card.png") -> str:
    """Renders a 1200x675 dark-mode technical comparison card with Pillow."""
    width, height = 1200, 675
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Slate-900
    draw = ImageDraw.Draw(img)

    font_badge = _load_font(20, bold=True)
    font_title = _load_font(34, bold=True)
    font_label = _load_font(21, bold=True)
    font_code = _load_font(18, mono=True)
    font_metric = _load_font(22, bold=True)

    # Series Pill Badge (dynamically sized so long track names never overflow)
    badge_text = data.get("series_badge", "🔥 30 DAYS • 30 HIDDEN CONCEPTS")
    badge_box = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_right = min(max(75 + (badge_box[2] - badge_box[0]) + 20, 420), width - 60)
    draw.rounded_rectangle([60, 38, badge_right, 76], radius=8, fill=(30, 41, 59), outline=(245, 158, 11), width=2)
    draw.text((75, 46), badge_text, fill=(251, 191, 36), font=font_badge)

    # Title (wrapped up to 2 lines cleanly)
    title_lines = textwrap.wrap(data.get("title", "Hidden Concept Breakdown"), width=48)[:2]
    title_y = 92
    for line in title_lines:
        draw.text((60, title_y), line, fill=(248, 250, 252), font=font_title)
        title_y += 40

    # Comparison Boxes
    box_w, y_start = 515, max(title_y + 18, 175)
    box_bottom = 545

    boxes = [
        (
            60,
            (239, 68, 68),
            (127, 29, 29),
            data.get("bad_label", "❌ COMMON PATTERN"),
            (254, 202, 202),
            _wrap_code_block(data.get("bad_code", "// standard way")),
        ),
        (
            625,
            (16, 185, 129),
            (6, 95, 70),
            data.get("good_label", "✅ HIDDEN GEM"),
            (167, 243, 208),
            _wrap_code_block(data.get("good_code", "// hidden pattern")),
        ),
    ]
    for x_left, outline_c, header_c, label, label_c, code_text in boxes:
        draw.rounded_rectangle([x_left, y_start, x_left + box_w, box_bottom], radius=12, fill=(30, 41, 59), outline=outline_c, width=2)
        draw.rounded_rectangle([x_left, y_start, x_left + box_w, y_start + 45], radius=10, fill=header_c)
        draw.text((x_left + 20, y_start + 12), label, fill=label_c, font=font_label)
        draw.multiline_text((x_left + 20, y_start + 62), code_text, fill=(241, 245, 249), font=font_code, spacing=8)

    # Bottom Metric Banner
    metric_text = data.get("key_metric", "⚡ Production Tested • 100% Practical")
    metric_line = textwrap.shorten(metric_text, width=82, placeholder="...")
    draw.rounded_rectangle([60, 568, 1140, 628], radius=10, fill=(17, 24, 39), outline=(71, 85, 105), width=1)
    draw.text((85, 586), metric_line, fill=(52, 211, 153), font=font_metric)

    img.save(output_path, "PNG")
    print(f"Generated 30-day series card: {output_path}")
    return output_path


def _linkedin_headers(access_token: str) -> dict[str, str]:
    api_version = os.environ.get("LINKEDIN_API_VERSION", "").strip() or DEFAULT_LINKEDIN_API_VERSION
    return {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": api_version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def upload_image_to_linkedin(access_token: str, author_urn: str, image_path: str) -> str:
    """Uploads image binary to LinkedIn and returns urn:li:image:..."""
    init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
    payload = {"initializeUploadRequest": {"owner": author_urn}}

    resp = requests.post(init_url, headers=_linkedin_headers(access_token), json=payload, timeout=30)
    _raise_for_status_with_body(resp, "LinkedIn initializeUpload", secret=access_token)
    data = resp.json()["value"]
    upload_url = data["uploadUrl"]
    image_urn = data["image"]

    with open(image_path, "rb") as f:
        upload_resp = requests.put(upload_url, headers={"Content-Type": "image/png"}, data=f, timeout=60)
        _raise_for_status_with_body(upload_resp, "LinkedIn image PUT")

    print(f"Uploaded to LinkedIn. Image URN: {image_urn}")
    return image_urn


def post_to_linkedin(
    access_token: str,
    author_urn: str,
    post_text: str,
    image_urn: str | None = None,
) -> str:
    """Publishes commentary with optional image to LinkedIn."""
    cleaned_text = _clean_post_for_linkedin(post_text)
    escaped_commentary = escape_linkedin_little_text(cleaned_text)
    if len(escaped_commentary) > MAX_LINKEDIN_POST_CHARS:
        raise ValueError(
            f"Escaped post commentary is {len(escaped_commentary)} chars "
            f"(LinkedIn limit is {MAX_LINKEDIN_POST_CHARS})."
        )

    url = "https://api.linkedin.com/rest/posts"
    payload: dict = {
        "author": author_urn,
        "commentary": escaped_commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    if image_urn:
        payload["content"] = {
            "media": {
                "id": image_urn,
                "title": "30 Days 30 Hidden Concepts",
            }
        }

    response = requests.post(url, headers=_linkedin_headers(access_token), json=payload, timeout=30)
    if response.status_code in (200, 201):
        post_urn = response.headers.get("x-restli-id", "Success")
        print(f"Successfully published to LinkedIn! URN: {post_urn}")
        return post_urn

    print(f"Failed to post to LinkedIn. Status: {response.status_code}", file=sys.stderr)
    print(response.text, file=sys.stderr)
    response.raise_for_status()
    return ""


# ---------------------------------------------------------------------------
# CLI Command Handlers
# ---------------------------------------------------------------------------
def handle_generate(track: str | None = None, day: int | None = None) -> None:
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        print("Error: GEMINI_API_KEY is required for generation.", file=sys.stderr)
        sys.exit(1)

    print("Generating 30-day series post draft...")
    data = generate_visual_post_data(gemini_key, track, day)

    with open("draft_content.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    image_path = "post_card.png"
    create_visual_card(data, image_path)

    print("\n--- 30-Day Series Draft Ready ---")
    print(f"Badge: {data.get('series_badge')}")
    print(f"Title: {data.get('title')}")
    print(f"Image: {image_path}")


def handle_publish(
    text_override: str | None = None,
    text_file: str | None = None,
    image_override: str | None = None,
) -> None:
    linkedin_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
    linkedin_urn = os.environ.get("LINKEDIN_AUTHOR_URN", "").strip()

    if not linkedin_token or not linkedin_urn:
        print("Error: LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN are required.", file=sys.stderr)
        sys.exit(1)

    post_text = Path(text_file).read_text(encoding="utf-8").strip() if text_file else text_override
    image_path = image_override or "post_card.png"

    current_data = {}
    if os.path.exists("draft_content.json"):
        with open("draft_content.json", "r", encoding="utf-8") as f:
            current_data = json.load(f)
            if not post_text:
                post_text = current_data.get("post_text")

    if not post_text or not post_text.strip():
        print("Error: No post text provided and draft_content.json not found.", file=sys.stderr)
        sys.exit(1)

    image_urn = None
    if os.path.exists(image_path):
        try:
            image_urn = upload_image_to_linkedin(linkedin_token, linkedin_urn, image_path)
        except Exception as e:
            print(f"Warning: Image upload failed ({e}). Posting text only.", file=sys.stderr)

    post_to_linkedin(linkedin_token, linkedin_urn, post_text, image_urn)

    # Increment day in series_state.json upon successful publish
    state = load_state()
    current_day = current_data.get("day", state.get("day", 1))
    next_day = current_day + 1
    if next_day > 30:
        tracks = ["dotnet", "angular", "sql_server"]
        curr_idx = tracks.index(state.get("track", "dotnet")) if state.get("track", "dotnet") in tracks else 0
        state["track"] = tracks[(curr_idx + 1) % len(tracks)]
        state["day"] = 1
    else:
        state["day"] = next_day
    save_state(state)
    print(f"Updated series state: Next is Track '{state['track']}', Day {state['day']}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="30 Days 30 Hidden Concepts LinkedIn Bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_parser = subparsers.add_parser("generate", help="Generate post draft & visual card")
    gen_parser.add_argument("--track", choices=["dotnet", "angular", "sql_server"], help="Specific technology track")
    gen_parser.add_argument("--day", type=int, help="Day number (1-30)")

    pub_parser = subparsers.add_parser("publish", help="Publish approved draft to LinkedIn")
    pub_parser.add_argument("--text", help="Custom text or override to publish")
    pub_parser.add_argument("--text-file", help="Path to UTF-8 text file to publish")
    pub_parser.add_argument("--image", help="Custom image path to upload")

    args = parser.parse_args()

    if args.command == "generate":
        handle_generate(args.track, args.day)
    elif args.command == "publish":
        handle_publish(args.text, args.text_file, args.image)


if __name__ == "__main__":
    main()