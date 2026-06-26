"""
diagnose.py — Run this in your MoneyPrinterTurbo-main folder
It tests every single component and tells you exactly what's broken.

Run with:
    python diagnose.py
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from autobot folder if it exists
for env_path in [Path(".env"), Path("../autobot/.env"), Path("autobot/.env")]:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")
        break

PASS = "  [PASS]"
FAIL = "  [FAIL]"
WARN = "  [WARN]"

results = []

def check(name, passed, detail=""):
    symbol = PASS if passed else FAIL
    msg = f"{symbol} {name}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((name, passed, detail))
    return passed


print("\n" + "="*60)
print("AutoBot Diagnostics")
print("="*60)

# ── 1. MoneyPrinterTurbo API ──────────────────────────────────
print("\n[1] MoneyPrinterTurbo API")

mpt_url = os.getenv("MPT_API_URL", "http://127.0.0.1:8080")
try:
    resp = requests.get(f"{mpt_url}/api/v1/tasks", timeout=5)
    check("API reachable", resp.status_code == 200, f"GET /api/v1/tasks → {resp.status_code}")
except Exception as e:
    check("API reachable", False, f"Cannot reach {mpt_url} — is 'python main.py' running?")

# Test actual video submission
try:
    payload = {
        "video_subject": "diagnostic test",
        "video_script": "This is a test.",
        "video_terms": "",
        "video_aspect": "9:16",
        "video_concat_mode": "random",
        "video_transition_mode": "None",
        "video_clip_duration": 5,
        "video_count": 1,
        "video_source": "pexels",
        "video_materials": [],
        "custom_audio_file": "",
        "video_language": "",
        "voice_name": "en-US-BrianNeural-Male",
        "voice_volume": 1,
        "voice_rate": 1,
        "bgm_type": "random",
        "bgm_file": "",
        "bgm_volume": 0.2,
        "subtitle_enabled": True,
        "subtitle_position": "bottom",
        "custom_position": 70,
        "font_name": "MicrosoftYaHeiBold.ttc",
        "text_fore_color": "#FFFFFF",
        "text_background_color": True,
        "font_size": 60,
        "stroke_color": "#000000",
        "stroke_width": 1.5,
        "n_threads": 2,
        "paragraph_number": 1,
    }
    resp = requests.post(f"{mpt_url}/api/v1/videos", json=payload, timeout=10)
    if resp.status_code == 200:
        task_id = resp.json().get("data", {}).get("task_id", "")
        check("Video task submission", True, f"task_id: {task_id}")
    else:
        check("Video task submission", False, f"Status {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    check("Video task submission", False, str(e))

# ── 2. Storage path ───────────────────────────────────────────
print("\n[2] Storage / Output Path")

video_dir = os.getenv("MPT_VIDEO_DIR", "")
candidates = [
    Path(video_dir) if video_dir else None,
    Path(".") / "storage" / "tasks",
    Path("..") / "MoneyPrinterTurbo-main" / "storage" / "tasks",
    Path("storage") / "tasks",
]

found_dir = None
for c in candidates:
    if c and c.exists():
        found_dir = c
        break

if found_dir:
    check("Storage/tasks folder exists", True, str(found_dir.resolve()))
    mp4_files = list(found_dir.rglob("*.mp4"))
    check("Previous videos exist", len(mp4_files) > 0,
          f"Found {len(mp4_files)} mp4 files" if mp4_files else "No mp4 files found yet — that's OK on first run")
else:
    check("Storage/tasks folder exists", False,
          f"MPT_VIDEO_DIR='{video_dir}' not found. Check the path in .env")

# ── 3. YouTube credentials ────────────────────────────────────
print("\n[3] YouTube Upload")

yt_enabled = os.getenv("UPLOAD_YOUTUBE", "false").lower() == "true"
check("UPLOAD_YOUTUBE=true", yt_enabled, "Set UPLOAD_YOUTUBE=true in .env" if not yt_enabled else "")

client_id     = os.getenv("YOUTUBE_CLIENT_ID", "")
client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "")
refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

check("YOUTUBE_CLIENT_ID set", bool(client_id), "Missing from .env" if not client_id else client_id[:20] + "...")
check("YOUTUBE_CLIENT_SECRET set", bool(client_secret), "Missing from .env" if not client_secret else "****" + client_secret[-4:])

token_clean = refresh_token.strip().strip('"').strip("'")
has_bad_chars = refresh_token != token_clean
check("YOUTUBE_REFRESH_TOKEN set", bool(token_clean),
      "Missing from .env" if not token_clean else token_clean[:20] + "...")
if has_bad_chars:
    print(f"  {WARN} Refresh token has extra quotes/spaces — remove them!")

# Test token actually works
if client_id and client_secret and token_clean:
    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     client_id,
                "client_secret": client_secret,
                "refresh_token": token_clean,
                "grant_type":    "refresh_token",
            },
            timeout=10,
        )
        data = resp.json()
        if "access_token" in data:
            check("YouTube token valid (can get access token)", True, "Token exchange successful")
        else:
            check("YouTube token valid (can get access token)", False,
                  f"Error: {data.get('error')} — {data.get('error_description', '')}")
    except Exception as e:
        check("YouTube token valid", False, str(e))

# Check google library installed
try:
    from googleapiclient.discovery import build
    check("google-api-python-client installed", True)
except ImportError:
    check("google-api-python-client installed", False,
          "Run: pip install google-api-python-client google-auth")

# ── 4. OpenRouter / LLM ───────────────────────────────────────
print("\n[4] LLM (OpenRouter)")

# Read from config.toml
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

llm_key = ""
if tomllib:
    for cfg_path in [Path("config.toml"), Path("../MoneyPrinterTurbo-main/config.toml")]:
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                cfg = tomllib.load(f)
            llm_key = cfg.get("app", {}).get("openai_api_key", "")
            llm_url = cfg.get("app", {}).get("openai_base_url", "")
            llm_model = cfg.get("app", {}).get("openai_model_name", "")
            check("config.toml found", True, str(cfg_path.resolve()))
            check("LLM API key set", bool(llm_key), llm_key[:12] + "..." if llm_key else "Not set")
            check("LLM base URL set", bool(llm_url), llm_url if llm_url else "Not set")
            break
else:
    print(f"  {WARN} Cannot read config.toml (tomllib not available)")

# ── 5. Pexels ─────────────────────────────────────────────────
print("\n[5] Pexels API")

if tomllib:
    for cfg_path in [Path("config.toml"), Path("../MoneyPrinterTurbo-main/config.toml")]:
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                cfg = tomllib.load(f)
            pexels_keys = cfg.get("app", {}).get("pexels_api_keys", [])
            if pexels_keys:
                key = pexels_keys[0]
                try:
                    resp = requests.get(
                        "https://api.pexels.com/videos/search?query=dog&per_page=1",
                        headers={"Authorization": key},
                        timeout=10,
                    )
                    check("Pexels API key valid", resp.status_code == 200,
                          f"Status {resp.status_code}" if resp.status_code != 200 else "Working")
                except Exception as e:
                    check("Pexels API key valid", False, str(e))
            else:
                check("Pexels API key configured", False, "No pexels_api_keys in config.toml")
            break

# ── Summary ───────────────────────────────────────────────────
print("\n" + "="*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f"Results: {passed} passed, {failed} failed")

if failed == 0:
    print("Everything looks good! Run python bot.py")
else:
    print("\nFix the [FAIL] items above, then run python bot.py again.")
print("="*60 + "\n")
