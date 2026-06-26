"""
video_generator.py v2 — fixed payload matching exact API schema
"""

import os
import time
import logging
import requests
from pathlib import Path
from typing import Tuple, Optional

log = logging.getLogger("autobot.generator")

MPT_API   = os.getenv("MPT_API_URL", "http://127.0.0.1:8080")
VIDEO_DIR = Path(os.getenv("MPT_VIDEO_DIR", "../MoneyPrinterTurbo-main/storage/tasks"))



def _generate_retention_script(topic: str) -> str:
    """Pre-generate a retention-optimized script before sending to API.
    If this fails, the API falls back to its own internal generation."""
    try:
        import os
        prompt = (
            f'''Write a 45-60 second viral short-form video script about: "{topic}"

STRICT RULES:
- First sentence: drop the most shocking fact immediately, no intro
- Include exactly 3 surprising specific facts about the topic
- Final sentence must be: "Follow for more facts like this"
- No markdown, no formatting, plain spoken words only
- Under 120 words total
- Do not mention the topic title directly, just tell the facts

Write only the script, nothing else:''')

        base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        api_key  = os.getenv("OPENAI_API_KEY", "")
        model    = os.getenv("OPENAI_MODEL_NAME", "openrouter/auto")

        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 250,
            },
            timeout=20,
        )
        if resp.status_code == 200:
            script = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean any markdown
            script = script.replace("*", "").replace("#", "")
            log.info(f"Pre-generated script ({len(script)} chars)")
            return script
    except Exception as e:
        log.warning(f"Script pre-generation failed: {e}, falling back to API default")
    return ""


def generate_video(topic: str) -> Tuple[Optional[Path], str, str]:
    log.info(f"Generating video: '{topic}'")

    title       = _make_title(topic)
    description = _make_description(topic)

    # Exact payload matching the API's own example schema
    payload = {
        "video_subject":         topic,
        "video_script":          _generate_retention_script(topic),
        "video_terms":           "",
        "video_aspect":          "9:16",
        "video_concat_mode":     "random",
        "video_transition_mode": "None",
        "video_clip_duration":   int(os.getenv("CLIP_DURATION", "5")),
        "video_count":           1,
        "video_source":          os.getenv("VIDEO_SOURCE", "pexels"),
        "video_materials":       [],
        "custom_audio_file":     "",
        "video_language":        "",
        "voice_name":            os.getenv("VOICE_NAME", "en-US-JennyNeural"),
        "voice_volume":          1,
        "voice_rate":            float(os.getenv("VOICE_RATE", "1.15")),
        "bgm_type":              "random",
        "bgm_file":              "",
        "bgm_volume":            0.2,
        "subtitle_enabled":      True,
        "subtitle_position":     "bottom",
        "custom_position":       70,
        "font_name":             "MicrosoftYaHeiBold.ttc",
        "text_fore_color":       "#FFFFFF",
        "text_background_color": True,
        "font_size":             60,
        "stroke_color":          "#000000",
        "stroke_width":          1.5,
        "n_threads":             2,
        "paragraph_number":      1,
    }

    # ── Submit task ────────────────────────────────────────────
    try:
        resp = requests.post(
            f"{MPT_API}/api/v1/videos",
            json=payload,
            timeout=30
        )
        if resp.status_code != 200:
            log.error(f"API {resp.status_code}: {resp.text}")
            return None, "", ""

        data    = resp.json()
        task_id = (data.get("data") or {}).get("task_id") or data.get("task_id")
        if not task_id:
            log.error(f"No task_id in response: {data}")
            return None, "", ""
        log.info(f"Task submitted: {task_id}")

    except Exception as e:
        log.error(f"Failed to submit task: {e}")
        return None, "", ""

    # ── Poll for completion ────────────────────────────────────
    max_wait   = int(os.getenv("MAX_WAIT_SECONDS", "600"))
    poll_every = 10
    waited     = 0

    while waited < max_wait:
        time.sleep(poll_every)
        waited += poll_every
        try:
            resp  = requests.get(f"{MPT_API}/api/v1/tasks/{task_id}", timeout=15)
            task  = resp.json().get("data", {})
            state = str(task.get("state", ""))
            log.info(f"  [{waited}s] state: {state}")

            if state in ("complete", "completed", "1", "2"):
                video_path = _find_output_video(task_id)
                if video_path:
                    log.info(f"Video ready: {video_path}")
                    return video_path, title, description
                log.error("Task complete but no video file found.")
                return None, "", ""

            elif state in ("failed", "error", "-1", "3"):
                log.error(f"Task failed: {task.get('message', 'no message')}")
                return None, "", ""

        except Exception as e:
            log.warning(f"Poll error: {e}")

    log.error(f"Timed out after {max_wait}s")
    return None, "", ""


def _find_output_video(task_id: str) -> Optional[Path]:
    candidates = [
        VIDEO_DIR / task_id,
        Path(".") / "storage" / "tasks" / task_id,
        Path("..") / "MoneyPrinterTurbo-main" / "storage" / "tasks" / task_id,
    ]
    for task_dir in candidates:
        if task_dir.exists():
            for pattern in ["final-1.mp4", "final-*.mp4", "*.mp4"]:
                matches = sorted(task_dir.glob(pattern))
                if matches:
                    return matches[0]
    log.warning(f"Could not find video for task {task_id}")
    return None


def _make_title(topic: str) -> str:
    topic = topic.strip().rstrip(".")
    for prefix in ["LPT: ", "TIL ", "TIL: "]:
        if topic.upper().startswith(prefix.upper()):
            topic = topic[len(prefix):]
            topic = topic[0].upper() + topic[1:]
    return topic[:100]


def _make_description(topic: str) -> str:
    niche = os.getenv("CONTENT_NICHE", "")
    base  = "#shorts #viral #facts #didyouknow #fyp #foryou #trending"
    extra = {
        "finance":  "#finance #money #investing #personalfinance",
        "animals":  "#animals #nature #wildlife #animalfacts",
        "fitness":  "#fitness #health #workout #wellness",
        "science":  "#science #education #learneveryday",
        "history":  "#history #facts #historical",
        "tech":     "#tech #technology #ai #innovation",
        "":         "#learneveryday #education #funfacts",
    }.get(niche.lower(), "")
    return f"{topic}\n\n{base} {extra}".strip()
