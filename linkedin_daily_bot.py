"""
LinkedIn 30-Day Series Bot: Hidden & Underused Concepts
=======================================================
Covers 30 Days of Hidden Concepts for .NET, Angular, and SQL Server.
Automatically tracks "Day X of 30", generates 4:5 editorial gradient-glass
visual cards, and publishes to LinkedIn upon approval.

Hybrid Curriculum + Live Market Radar:
- Cycle 1 (Days 1-90): Structured hidden gems from thirty_days_curriculum.json
- Cycle 2+ (or --dynamic): Live Google Search Grounding for recent releases
  and market trends, deduplicated against post_history.json.

Enforces high-retention technical bullet pattern:
- **[Tech Anchor]:** [Exact metric, performance difference, or code trade-off]

Usage:
  python linkedin_daily_bot.py generate [--track dotnet|angular|sql_server] [--day N] [--dynamic]
  python linkedin_daily_bot.py publish [--text "..." | --text-file FILE] [--image "..."]
"""

from __future__ import annotations

import argparse
import json
import math
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
HISTORY_FILE = "post_history.json"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash")
TRANSIENT_GEMINI_STATUS_CODES = (429, 500, 502, 503, 504)
MODEL_FALLBACK_STATUS_CODES = (400, 404, 429, 500, 502, 503, 504)
DEFAULT_LINKEDIN_API_VERSION = "202610"
MAX_LINKEDIN_POST_CHARS = 3000

_PRESERVED_LITTLE_TOKEN_RE = re.compile(
    r"@\[[^\]]+\]\(urn:li:[^)]+\)"
    r"|\{hashtag\|[^}]+\}"
    r"|(?:(?<=^)|(?<=\s))#[A-Za-z][A-Za-z0-9_]*"
)
_LITTLE_RESERVED_CHARS_RE = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_CARD_UNSUPPORTED_EMOJI_RE = re.compile(r"[\u2600-\u27BF\uFE00-\uFE0F\U00010000-\U0010FFFF]")
TRACK_HASHTAGS = {
    "dotnet": "#DotNet #CSharp #Performance #BackendDevelopment #SoftwareEngineering",
    "angular": "#Angular #TypeScript #Frontend #WebDevelopment #SoftwareEngineering",
    "sql_server": "#SQLServer #TSQL #DatabasePerformance #DataEngineering #SoftwareEngineering",
}

# Per-track editorial gradient palettes (base, glow1, glow2, accent_text, pill_bg)
_TRACK_PALETTES = {
    "dotnet": {
        "base": (13, 12, 29),
        "glow1": (67, 56, 202),
        "glow2": (49, 27, 92),
        "accent": (196, 181, 253),   # Lavender
        "kicker": (165, 180, 252),
        "pill_bg": (99, 102, 241),
    },
    "angular": {
        "base": (18, 11, 30),
        "glow1": (157, 23, 77),
        "glow2": (55, 48, 163),
        "accent": (253, 164, 175),   # Soft Rose
        "kicker": (244, 114, 182),
        "pill_bg": (219, 39, 119),
    },
    "sql_server": {
        "base": (9, 17, 30),
        "glow1": (14, 116, 144),
        "glow2": (49, 46, 129),
        "accent": (125, 211, 252),   # Sky Blue
        "kicker": (56, 189, 248),
        "pill_bg": (2, 132, 199),
    },
}

# Syntax highlighting token sets for C#, TypeScript/Angular, and T-SQL
_KEYWORDS = {
    "private", "public", "protected", "internal", "static", "readonly", "const",
    "var", "let", "new", "return", "async", "await", "if", "else", "for", "foreach",
    "while", "switch", "case", "break", "class", "record", "struct", "interface",
    "void", "int", "string", "bool", "char", "byte", "using", "namespace", "export",
    "import", "from", "function", "true", "false", "null", "undefined", "this",
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "CREATE", "INDEX", "ON", "INCLUDE", "WITH", "AS", "AND", "OR", "NOT", "IN",
    "ORDER", "BY", "OFFSET", "ROWS", "FETCH", "NEXT", "ONLY", "TOP", "JOIN", "INNER",
    "LEFT", "CROSS", "APPLY", "OUTPUT", "INSERTED", "DELETED", "BEGIN", "END", "EXEC",
    "select", "from", "where", "insert", "into", "values", "update", "set", "delete",
    "create", "index", "on", "include", "with", "as", "and", "or", "not", "in",
    "order", "by", "offset", "rows", "fetch", "next", "only", "top", "join", "cross",
    "apply", "output", "inserted", "deleted",
}

_TOKEN_RE = re.compile(
    r"(//[^\n]*|--[^\n]*)"                        # Comments
    r"|(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"  # Strings / chars
    r"|(@?[A-Za-z_][A-Za-z0-9_]*)"                # Identifiers / keywords / types
    r"|(\b\d+(?:\.\d+)?\b)"                       # Numbers
    r"|([^\sA-Za-z0-9_\"']+|\s+)"                 # Punctuation / whitespace
)


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("cycle", 1)
                return data
        except Exception:
            pass
    return {"track": "dotnet", "day": 1, "cycle": 1}


def save_state(state: dict) -> None:
    tmp_path = f"{STATE_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, STATE_FILE)


def load_history() -> list[str]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
                return items if isinstance(items, list) else []
        except Exception:
            pass
    return []


def save_history(items: list[str]) -> None:
    tmp_path = f"{HISTORY_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(items[-120:], f, indent=2)
        f.write("\n")
    os.replace(tmp_path, HISTORY_FILE)


def get_current_item(track: str | None = None, day: int | None = None) -> tuple:
    state = load_state()
    active_track = track or state.get("track", "dotnet")
    active_day = day or state.get("day", 1)
    active_cycle = int(state.get("cycle", 1))

    with open(CURRICULUM_FILE, "r", encoding="utf-8") as f:
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
    return active_track, item["day"], track_display, item, active_cycle


_UNICODE_BOLD_MAP = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
    "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
    "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
    "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
)


def _to_unicode_bold(text: str) -> str:
    return text.translate(_UNICODE_BOLD_MAP)


def _clean_post_for_linkedin(text: str) -> str:
    """Strip inline code blocks and convert Markdown into crisp LinkedIn-ready Unicode bold."""
    cleaned = re.sub(
        r"(?ms)^(?:Before|After):[ \t]*\n```[A-Za-z0-9_-]*[ \t]*\n.*?\n```[ \t]*\n?",
        "",
        text,
    )
    cleaned = re.sub(r"(?ms)^```[A-Za-z0-9_-]*[ \t]*\n.*?\n```[ \t]*\n?", "", cleaned)
    cleaned = re.sub(r"(?m)^Why it matters:[ \t]*\n?", "", cleaned)
    cleaned = re.sub(r"\*\*([^*\n]+?)\*\*", lambda m: _to_unicode_bold(m.group(1)), cleaned)
    cleaned = re.sub(r"(?m)^(Day\s+\d+/\d+\s*[—-].+)$", lambda m: _to_unicode_bold(m.group(1)), cleaned)
    cleaned = re.sub(r"(?m)^(Watch out:)", lambda m: _to_unicode_bold(m.group(1)), cleaned)
    cleaned = re.sub(r"(?m)^•\s+", "▸ ", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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
    retry_delays = (3.0, 6.0)

    for idx, model in enumerate(models_to_try):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        has_next_model = idx + 1 < len(models_to_try)

        for attempt in range(len(retry_delays) + 1):
            response: requests.Response | None = None
            last_exc: requests.RequestException | None = None
            retry_reason: str | None = None

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)
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


def generate_visual_post_data(
    api_key: str,
    track: str | None = None,
    day: int | None = None,
    dynamic: bool = False,
) -> dict:
    """Calls Gemini API to generate editorial card data and practitioner LinkedIn post copy."""
    active_track, day_num, track_display, item, active_cycle = get_current_item(track, day)
    use_dynamic = dynamic or active_cycle >= 2
    configured_model = os.environ.get("GEMINI_MODEL", "").strip()
    models_to_try = [configured_model] if configured_model else list(FALLBACK_GEMINI_MODELS)
    clean_key = api_key.strip().strip('"').strip("'")
    hashtags = TRACK_HASHTAGS.get(
        active_track,
        "#SoftwareEngineering #Performance #CleanCode #WebDevelopment",
    )

    if use_dynamic:
        history = load_history()
        recent_list = ", ".join(history[-30:]) if history else "None yet"
        topic_block = (
            f"Mode: LIVE MARKET RADAR (Cycle {active_cycle}).\n"
            f"Use Google Search to find a genuinely recent, high-impact {track_display} release feature, "
            f"runtime/framework improvement, or modern production pattern that developers are adopting right now.\n"
            f"DO NOT repeat any of these previously covered topics: {recent_list}."
        )
        badge_line = f"MARKET RADAR  •  {track_display.upper()}  •  DAY {day_num:02d}"
        title_hint = f"Concise 3-6 word topic title in {track_display}"
    else:
        topic_block = f"Today's Concept: {item['concept']}\nTechnical Focus: {item['focus']}"
        badge_line = f"30 DAYS OF HIDDEN {track_display.upper()} GEMS  •  DAY {day_num:02d}"
        title_hint = item["concept"]

    system_prompt = f"""
You are a Senior Fullstack Engineer (.NET, Angular, SQL Server) writing Day {day_num} of your personal LinkedIn engineering series:
"Day {day_num}/30: {track_display} Hidden Concepts".

{topic_block}

Voice & Tone Rules (CRITICAL - sound like a real practitioner, NOT an AI):
- Keep `post_text` minimal and scannable (STRICTLY under 90 words): DO NOT put code blocks in `post_text` because the visual card already shows both Before and After code.
- Write like a senior dev sharing a quick field note from a real code review or profiler session.
- Ground claims in real runtime/DB mechanics (e.g., heap allocations, Gen0 GC, logical reads, Index Seek vs Key Lookup, change detection cycles).
- NEVER use AI clichés or marketing hype: NO "completely missing out", "drastically cut down", "delivers up to 10x", "skyrocket", "unlock", "game-changer", "leverage", "leverages", "leveraged", "utilize", "delve", "elevate", or "in today's fast-paced world".
- Include one concise, honest `Watch out:` line naming a real production edge case or caveat.
- Code accuracy: Verify exact C#/Angular/T-SQL API signatures (e.g. `SearchValues<T>` requires `input.AsSpan().ContainsAny(...)`, not `string.ContainsAny(...)`), and avoid `\r`, `\n`, `\t` escape literals inside sample strings—use visible chars like `','`, `';'`, `'/'`, `'?'` instead.

Visual Card Data Rules (for our 4:5 editorial Gradient-Glass image template showing BOTH Before and After):
- headline_line1: Short bold white hook (3-5 words, e.g. "Stop allocating arrays")
- headline_accent: Short colored continuation (4-6 words max so it never clips, e.g. "for repeated char lookups.")
- pill_tag: Short feature/API pill (e.g. "SearchValues<char>")
- pill_badge: Short version tag (e.g. "NET 8+", "ANGULAR 19", "SQL 2019+")
- code_filename: Realistic short filename for the snippet header (e.g. "SearchValuesDemo.cs", "signal-store.ts", "query.sql")
- card_highlights: Exactly 3 ultra-short metric/takeaway boxes:
  [
    {{"stat": "0 B", "label": "Heap allocations per lookup"}},
    {{"stat": "SIMD", "label": "Vectorized CPU instructions"}},
    {{"stat": "Span", "label": "Works directly on slices"}}
  ]
- bad_code: 3 to 4 lines of realistic suboptimal code (keep each line <= 48 chars).
- good_code: 4 to 5 lines of production-accurate optimized code (keep each line <= 48 chars).
- Do NOT put emojis inside any card fields (headline, pill_tag, card_highlights, bad_code, good_code, subtitle, code_filename).

MANDATORY POST COMMENTARY BULLET RULE:
Every bullet point under the takeaway section MUST strictly follow this exact syntax (NEVER output literal square brackets [ or ] around the anchor or text):
• **Tech Anchor:** One short sentence with a real profiler/runtime metric or trade-off

Use double newlines (`\\n\\n`) between every paragraph and section in `post_text` so it breathes nicely on LinkedIn.

Return STRICT RAW JSON ONLY (no markdown fences) with these keys:
{{
  "series_badge": "{badge_line}",
  "title": "{title_hint}",
  "headline_line1": "3-5 word white headline",
  "headline_accent": "4-6 word accent headline continuation",
  "subtitle": "Crisp 8-12 word engineering summary",
  "pill_tag": "Core API or feature name",
  "pill_badge": "Version tag (e.g. NET 8+)",
  "code_filename": "Short realistic filename (.cs, .ts, or .sql)",
  "card_highlights": [
    {{"stat": "Short stat", "label": "4-6 word description"}},
    {{"stat": "Short stat", "label": "4-6 word description"}},
    {{"stat": "Short stat", "label": "4-6 word description"}}
  ],
  "bad_code": "3 to 4 lines of realistic suboptimal code",
  "good_code": "4 to 5 lines of realistic optimized code",
  "post_text": "Minimal ready-to-post LinkedIn text (STRICTLY under 90 words, NO code blocks) structured as:\\n\\nDay {day_num}/30 — [Concept Title] ({track_display})\\n\\n[1 punchy hook line from a real dev perspective]\\n\\n• **First Anchor:** Short profiler/runtime insight without brackets\\n• **Second Anchor:** Short profiler/runtime insight without brackets\\n• **Third Anchor:** Short profiler/runtime insight without brackets\\n\\nWatch out: [1 short sentence on a real production gotcha]\\n\\n[1 short peer question]\\n\\n{hashtags}"
}}
"""

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": clean_key,
    }
    if use_dynamic:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": system_prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.3},
        }
    else:
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
    data["dynamic"] = use_dynamic
    return data


def _strip_unsupported_emojis(text: str, preserve_newlines: bool = False) -> str:
    """Removes emojis unsupported by DejaVu/Arial so Pillow never renders □ tofu boxes."""
    cleaned = _CARD_UNSUPPORTED_EMOJI_RE.sub("", text or "")
    if preserve_newlines:
        return "\n".join(line.expandtabs(4).rstrip() for line in cleaned.splitlines())
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _load_font(size: int, mono: bool = False, bold: bool = False) -> ImageFont.ImageFont:
    if mono:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/System/Library/Fonts/Supplemental/Courier New.ttf",
            "/Library/Fonts/Courier New.ttf",
            "/System/Library/Fonts/Menlo.ttc",
        ]
    elif bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _make_mesh_bg(
    width: int,
    height: int,
    c_base: tuple[int, int, int],
    c_glow1: tuple[int, int, int],
    c_glow2: tuple[int, int, int],
) -> Image.Image:
    """Generates a smooth radial mesh gradient background (editorial style)."""
    sw, sh = width // 4, height // 4
    small = Image.new("RGB", (sw, sh), c_base)
    spx = small.load()
    sgx1, sgy1 = int(sw * 0.85), int(sh * 0.86)
    sgx2, sgy2 = int(sw * 0.16), int(sh * 0.18)
    sr1, sr2 = (width * 0.95) / 4.0, (width * 0.75) / 4.0

    for y in range(sh):
        for x in range(sw):
            d1 = math.hypot(x - sgx1, y - sgy1) / sr1
            d2 = math.hypot(x - sgx2, y - sgy2) / sr2
            w1 = max(0.0, 1.0 - d1) ** 2.1
            w2 = max(0.0, 1.0 - d2) ** 2.3
            r = min(255, int(c_base[0] + (c_glow1[0] - c_base[0]) * w1 + (c_glow2[0] - c_base[0]) * w2 * 0.55))
            g = min(255, int(c_base[1] + (c_glow1[1] - c_base[1]) * w1 + (c_glow2[1] - c_base[1]) * w2 * 0.55))
            b = min(255, int(c_base[2] + (c_glow1[2] - c_base[2]) * w1 + (c_glow2[2] - c_base[2]) * w2 * 0.55))
            spx[x, y] = (r, g, b)

    return small.resize((width, height), Image.Resampling.BICUBIC)


def _draw_glass_rect(
    base_img: Image.Image,
    xy: list[int],
    fill_rgba: tuple[int, int, int, int],
    outline_rgba: tuple[int, int, int, int],
    radius: int = 18,
) -> Image.Image:
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle(xy, radius=radius, fill=fill_rgba, outline=outline_rgba, width=2)
    return Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")


def _wrap_code_lines(code: str, max_chars: int = 46, max_lines: int = 8) -> list[str]:
    wrapped: list[str] = []
    for raw_line in (code or "").splitlines():
        if not raw_line.strip():
            wrapped.append("")
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        sub_indent = " " * min(indent + 4, 8)
        parts = textwrap.wrap(
            raw_line,
            width=max_chars,
            subsequent_indent=sub_indent,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped.extend(parts or [""])
    return wrapped[:max_lines]


def _draw_syntax_highlighted_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x_gutter: int,
    x_code: int,
    y_start: int,
    line_height: int,
    font_code: ImageFont.ImageFont,
) -> None:
    """Draws code lines with subtle line numbers and VS Code Dark+ syntax highlighting."""
    c_gutter = (100, 116, 139)
    c_comment = (148, 163, 184)
    c_string = (163, 230, 53)
    c_keyword = (192, 132, 252)
    c_type = (56, 189, 248)
    c_number = (251, 191, 36)
    c_default = (241, 245, 249)

    for idx, line in enumerate(lines, start=1):
        y = y_start + (idx - 1) * line_height
        draw.text((x_gutter, y), f"{idx:2d}", fill=c_gutter, font=font_code)

        x_cursor = x_code
        for m in _TOKEN_RE.finditer(line):
            tok = m.group(0)
            if m.group(1):
                color = c_comment
            elif m.group(2):
                color = c_string
            elif m.group(3):
                if tok in _KEYWORDS:
                    color = c_keyword
                elif tok[0].isupper() and len(tok) > 1:
                    color = c_type
                else:
                    color = c_default
            elif m.group(4):
                color = c_number
            else:
                color = c_default

            draw.text((x_cursor, y), tok, fill=color, font=font_code)
            if hasattr(draw, "textlength"):
                x_cursor += draw.textlength(tok, font=font_code)
            else:
                bbox = draw.textbbox((0, 0), tok, font=font_code)
                x_cursor += bbox[2] - bbox[0]


def create_visual_card(data: dict, output_path: str = "post_card.png") -> str:
    """Renders a 1080x1350 (4:5 portrait) editorial Gradient-Glass LinkedIn card."""
    width, height = 1080, 1350
    track = data.get("track", "dotnet")
    pal = _TRACK_PALETTES.get(track, _TRACK_PALETTES["dotnet"])

    img = _make_mesh_bg(width, height, pal["base"], pal["glow1"], pal["glow2"])
    draw = ImageDraw.Draw(img)

    font_kicker = _load_font(19, bold=False)
    font_pill = _load_font(22, bold=True)
    font_badge = _load_font(15, bold=True)
    font_h1 = _load_font(58, bold=True)
    font_sub = _load_font(25, bold=False)
    font_stat = _load_font(30, bold=True)
    font_stat_lbl = _load_font(18, bold=False)
    font_code = _load_font(19, mono=True)
    font_fname = _load_font(15, mono=True)
    font_brand = _load_font(24, bold=True)
    font_right = _load_font(22, bold=False)

    margin = 80
    day_num = int(data.get("day", 1))

    # 1. Top Eyebrow Kicker
    kicker = _strip_unsupported_emojis(data.get("series_badge", f"30 DAYS OF HIDDEN GEMS  •  DAY {day_num:02d}"))
    draw.text((margin, 64), kicker, fill=pal["kicker"], font=font_kicker)

    # 2. Pill Tag + Version Badge
    pill_tag = _strip_unsupported_emojis(data.get("pill_tag") or data.get("title", "Hidden Concept"))
    pill_badge = _strip_unsupported_emojis(data.get("pill_badge") or "")
    tag_w = draw.textlength(pill_tag, font=font_pill) if hasattr(draw, "textlength") else len(pill_tag) * 13
    badge_w = (draw.textlength(pill_badge, font=font_badge) + 28) if pill_badge else 0
    pill_total_w = int(min(tag_w + badge_w + (68 if pill_badge else 48), width - 2 * margin))

    img = _draw_glass_rect(
        img,
        [margin, 108, margin + pill_total_w, 156],
        fill_rgba=(*pal["pill_bg"], 75),
        outline_rgba=(*pal["kicker"], 150),
        radius=14,
    )
    draw = ImageDraw.Draw(img)
    draw.text((margin + 22, 119), pill_tag, fill=(248, 250, 252), font=font_pill)
    if pill_badge:
        bx0 = int(margin + 22 + tag_w + 16)
        bx1 = min(int(bx0 + badge_w), margin + pill_total_w - 14)
        draw.rounded_rectangle([bx0, 117, bx1, 147], radius=10, fill=pal["pill_bg"])
        draw.text((bx0 + 13, 123), pill_badge, fill=(255, 255, 255), font=font_badge)

    # 3. Two-Tone Editorial Headline
    h1_top = _strip_unsupported_emojis(data.get("headline_line1") or data.get("title", "Production Pattern"))
    h1_accent = _strip_unsupported_emojis(data.get("headline_accent") or "")
    y_h = 182
    for ln in textwrap.wrap(h1_top, width=25)[:2]:
        draw.text((margin, y_h), ln, fill=(248, 250, 252), font=font_h1)
        y_h += 66
    if h1_accent:
        for ln in textwrap.wrap(h1_accent, width=26)[:2]:
            draw.text((margin, y_h), ln, fill=pal["accent"], font=font_h1)
            y_h += 66

    # 4. Crisp Subtitle
    sub = _strip_unsupported_emojis(data.get("subtitle", ""))
    y_sub = y_h + 12
    if sub:
        for ln in textwrap.wrap(sub, width=58)[:2]:
            draw.text((margin, y_sub), ln, fill=(203, 213, 225), font=font_sub)
            y_sub += 34

    # 5. Three Glassmorphic Stat / Takeaway Cards
    highlights = data.get("card_highlights") or [
        {"stat": "Zero Alloc", "label": "No heap pressure in hot paths"},
        {"stat": "Cleaner", "label": "Idiomatic modern syntax"},
        {"stat": "Tested", "label": "Production-ready pattern"},
    ]
    highlights = highlights[:3]
    y_cards = max(y_sub + 22, 446)
    card_gap = 20
    card_w = (width - 2 * margin - card_gap * 2) // 3
    card_h = 122

    for idx, item in enumerate(highlights):
        cx0 = margin + idx * (card_w + card_gap)
        img = _draw_glass_rect(
            img,
            [cx0, y_cards, cx0 + card_w, y_cards + card_h],
            fill_rgba=(255, 255, 255, 18),
            outline_rgba=(255, 255, 255, 48),
            radius=16,
        )
        draw = ImageDraw.Draw(img)
        stat_txt = _strip_unsupported_emojis(str(item.get("stat", "")))[:14]
        lbl_txt = _strip_unsupported_emojis(str(item.get("label", "")))
        draw.text((cx0 + 20, y_cards + 18), stat_txt, fill=(248, 250, 252), font=font_stat)
        ly = y_cards + 62
        for ln in textwrap.wrap(lbl_txt, width=22)[:2]:
            draw.text((cx0 + 20, ly), ln, fill=(203, 213, 225), font=font_stat_lbl)
            ly += 22

    # 6. Stacked BEFORE & AFTER Frosted Code Windows
    default_fnames = {"dotnet": "Program.cs", "angular": "component.ts", "sql_server": "query.sql"}
    code_fname = _strip_unsupported_emojis(data.get("code_filename") or default_fnames.get(track, "snippet.cs"))
    bad_clean = _strip_unsupported_emojis(data.get("bad_code", "// legacy approach"), preserve_newlines=True)
    good_clean = _strip_unsupported_emojis(data.get("good_code", "// optimized pattern"), preserve_newlines=True)
    bad_lines = _wrap_code_lines(bad_clean, max_chars=52, max_lines=5)
    good_lines = _wrap_code_lines(good_clean, max_chars=52, max_lines=6)

    y_code_top = y_cards + card_h + 24
    y_code_bottom = height - 135
    box_gap = 18
    total_code_h = y_code_bottom - y_code_top - box_gap
    before_h = max(180, int(total_code_h * 0.44))
    y_before_end = y_code_top + before_h
    y_after_top = y_before_end + box_gap

    for panel_y0, panel_y1, badge_lbl, dot_col, border_col, lines, show_fname in (
        (y_code_top, y_before_end, "BEFORE", (239, 68, 68), (239, 68, 68, 95), bad_lines, False),
        (y_after_top, y_code_bottom, "AFTER", (16, 185, 129), (16, 185, 129, 110), good_lines, True),
    ):
        img = _draw_glass_rect(
            img,
            [margin, panel_y0, width - margin, panel_y1],
            fill_rgba=(10, 12, 26, 205),
            outline_rgba=border_col,
            radius=18,
        )
        draw = ImageDraw.Draw(img)
        draw.ellipse([margin + 22, panel_y0 + 18, margin + 34, panel_y0 + 30], fill=dot_col)
        draw.text((margin + 44, panel_y0 + 15), badge_lbl, fill=dot_col, font=font_badge)
        if show_fname:
            fn_w = draw.textlength(code_fname, font=font_fname) if hasattr(draw, "textlength") else len(code_fname) * 9
            draw.text((width - margin - 22 - fn_w, panel_y0 + 15), code_fname, fill=(148, 163, 184), font=font_fname)
        draw.line([(margin + 1, panel_y0 + 44), (width - margin - 1, panel_y0 + 44)], fill=(255, 255, 255, 25), width=1)
        avail_h = (panel_y1 - 12) - (panel_y0 + 56)
        line_h = min(33, max(24, avail_h // max(len(lines), 1)))
        _draw_syntax_highlighted_lines(
            draw,
            lines,
            margin + 22,
            margin + 64,
            panel_y0 + 58,
            line_h,
            font_code,
        )

    # 7. Minimal Editorial Footer
    fx, fy = margin, height - 96
    s, gap = 12, 4
    draw.rounded_rectangle([fx, fy, fx + s, fy + s], radius=3, fill=pal["pill_bg"])
    draw.rounded_rectangle([fx + s + gap, fy, fx + 2 * s + gap, fy + s], radius=3, fill=(56, 189, 248))
    draw.rounded_rectangle([fx, fy + s + gap, fx + s, fy + 2 * s + gap], radius=3, fill=(192, 132, 252))
    draw.rounded_rectangle([fx + s + gap, fy + s + gap, fx + 2 * s + gap, fy + 2 * s + gap], radius=3, fill=(52, 211, 153))
    draw.text((fx + 42, fy + 1), "@maayurdahake", fill=(248, 250, 252), font=font_brand)

    right_lbl = f"Day {day_num:02d} / 30  \u2192"
    rw = draw.textlength(right_lbl, font=font_right) if hasattr(draw, "textlength") else len(right_lbl) * 12
    draw.text((width - margin - rw, fy + 1), right_lbl, fill=(226, 232, 240), font=font_right)

    img.save(output_path, "PNG")
    print(f"Generated 4:5 editorial card: {output_path}")
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


def _extract_title_and_tags(post_text: str, track: str) -> tuple[str, list[str]]:
    first_line = next((ln.strip() for ln in post_text.splitlines() if ln.strip()), "Engineering Note")
    title = re.sub(r"^Day\s+\d+/\d+\s*[—-]\s*", "", first_line).strip()[:120]
    tag_map = {
        "dotnet": ["dotnet", "csharp", "performance", "programming"],
        "angular": ["angular", "typescript", "webdev", "frontend"],
        "sql_server": ["sqlserver", "sql", "database", "performance"],
    }
    return title, tag_map.get(track, ["programming", "softwareengineering"])


def post_to_devto(api_key: str, title: str, body_markdown: str, track: str, image_url: str | None = None) -> str:
    """Publishes Markdown article to Dev.to with full uncropped visual card."""
    _, tags = _extract_title_and_tags(body_markdown, track)
    full_body = f"![{title}]({image_url})\n\n{body_markdown}" if image_url else body_markdown
    article: dict = {
        "title": title,
        "published": True,
        "body_markdown": full_body,
        "tags": tags,
    }
    if image_url:
        article["main_image"] = image_url
    resp = requests.post(
        "https://dev.to/api/articles",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"article": article},
        timeout=30,
    )
    _raise_for_status_with_body(resp, "Dev.to API", secret=api_key)
    url = resp.json().get("url", "Published")
    print(f"Successfully published to Dev.to! URL: {url}")
    return url


# ---------------------------------------------------------------------------
# CLI Command Handlers
# ---------------------------------------------------------------------------
def handle_generate(track: str | None = None, day: int | None = None, dynamic: bool = False) -> None:
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        print("Error: GEMINI_API_KEY is required for generation.", file=sys.stderr)
        sys.exit(1)

    print("Generating 30-day series post draft...")
    data = generate_visual_post_data(gemini_key, track, day, dynamic=dynamic)

    with open("draft_content.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    image_path = "post_card.png"
    create_visual_card(data, image_path)

    print("\n--- 30-Day Series Draft Ready ---")
    print(f"Badge: {data.get('series_badge')}")
    print(f"Title: {data.get('title')}")
    print(f"Mode:  {'Live Market Radar' if data.get('dynamic') else 'Structured Curriculum'}")
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

    # Optional cross-posting (skips cleanly if secrets are not configured)
    state = load_state()
    active_track = current_data.get("track", state.get("track", "dotnet"))
    title, _ = _extract_title_and_tags(post_text, active_track)
    image_url = os.environ.get("PUBLIC_IMAGE_URL", "").strip() or None

    devto_key = os.environ.get("DEVTO_API_KEY", "").strip()
    if devto_key:
        try:
            post_to_devto(devto_key, current_data.get("title") or title, post_text, active_track, image_url)
        except Exception as e:
            print(f"Warning: Dev.to publish failed ({e})", file=sys.stderr)


    # Record published topic to prevent duplicates in future dynamic cycles
    published_title = current_data.get("title")
    if published_title:
        history = load_history()
        if published_title not in history:
            history.append(published_title)
            save_history(history)

    # Increment day (and cycle after completing all 3 tracks) upon successful publish
    state = load_state()
    current_day = current_data.get("day", state.get("day", 1))
    next_day = current_day + 1
    if next_day > 30:
        tracks = ["dotnet", "angular", "sql_server"]
        curr_idx = tracks.index(state.get("track", "dotnet")) if state.get("track", "dotnet") in tracks else 0
        next_idx = (curr_idx + 1) % len(tracks)
        state["track"] = tracks[next_idx]
        state["day"] = 1
        if next_idx == 0:
            state["cycle"] = int(state.get("cycle", 1)) + 1
    else:
        state["day"] = next_day
    save_state(state)
    print(f"Updated series state: Next is Cycle {state.get('cycle', 1)}, Track '{state['track']}', Day {state['day']}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="30 Days 30 Hidden Concepts LinkedIn Bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen_parser = subparsers.add_parser("generate", help="Generate post draft & visual card")
    gen_parser.add_argument("--track", choices=["dotnet", "angular", "sql_server"], help="Specific technology track")
    gen_parser.add_argument("--day", type=int, help="Day number (1-30)")
    gen_parser.add_argument("--dynamic", action="store_true", help="Use live Google Search grounding for trending market topics")

    pub_parser = subparsers.add_parser("publish", help="Publish approved draft to LinkedIn")
    pub_parser.add_argument("--text", help="Custom text or override to publish")
    pub_parser.add_argument("--text-file", help="Path to UTF-8 text file to publish")
    pub_parser.add_argument("--image", help="Custom image path to upload")

    args = parser.parse_args()

    if args.command == "generate":
        handle_generate(args.track, args.day, dynamic=args.dynamic)
    elif args.command == "publish":
        handle_publish(args.text, args.text_file, args.image)


if __name__ == "__main__":
    main()
