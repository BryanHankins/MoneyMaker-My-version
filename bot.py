"""
MoneyPrinterTurbo AutoBot
=========================
Posts one video, waits exactly 4 hours after it finishes, then posts the next.
No fixed clock times — each video chains to the next.

Run:   python bot.py
"""

import os
import sys
import time
import json
import logging
import random
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("autobot")

# ── Config ────────────────────────────────────────────────────────────────────
HOURS_BETWEEN    = int(os.getenv("HOURS_BETWEEN_VIDEOS", "4"))
UPLOAD_YOUTUBE   = os.getenv("UPLOAD_YOUTUBE",   "false").lower() == "true"
UPLOAD_TIKTOK    = os.getenv("UPLOAD_TIKTOK",    "false").lower() == "true"
UPLOAD_INSTAGRAM = os.getenv("UPLOAD_INSTAGRAM", "false").lower() == "true"
UPLOAD_FACEBOOK  = os.getenv("UPLOAD_FACEBOOK",  "false").lower() == "true"

hashtags = (
    "#shorts #fyp #health #healthfacts #bodyfacts #didyouknow #funfacts "
    "#sciencefacts #medicalfacts #healthtips #wellness #bodyhacks #brainfacts "
    "#humanbody #healthylifestyle #learnontiktok #educational #viral #trending #mindblowing"
)

prefixes = [
    "🔥 ",
    "😱 ",

]

# ── Cache cleanup ─────────────────────────────────────────────────────────────
def clean_cache():
    cache = Path("storage/cache_videos")
    if not cache.exists():
        return
    files = sorted(cache.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
    if len(files) > 500:
        for f in files[:100]:
            try:
                f.unlink()
            except Exception:
                pass
        log.info("Cache cleaned.")

# ── Single video pipeline ─────────────────────────────────────────────────────
def run_single_video(slot: int):
    log.info("=" * 60)
    log.info(f"🚀 Slot {slot} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    from trends import get_trending_topics
    from video_generator import generate_video
    from uploader import upload_to_all_platforms

    topics = get_trending_topics(count=1)
    if not topics:
        log.error("No topics found — skipping this slot.")
        return

    topic = topics[0]
    log.info(f"📈 Topic: '{topic}'")

    try:
        video_path, title, description = generate_video(topic)
        if not video_path:
            log.error(f"Video generation failed for '{topic}'")
            return

        title       = random.choice(prefixes) + title
        description = f"{title}\n\n{hashtags}"

        upload_results = upload_to_all_platforms(
            video_path=video_path,
            title=title,
            description=description,
            topic=topic,
        )

        report = log_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        report.write_text(json.dumps({
            "slot":    slot,
            "topic":   topic,
            "uploads": upload_results,
        }, indent=2))

        log.info(f"✅ Slot {slot} done: '{topic}'")

    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)

    clean_cache()

# ── Main loop — sequential, no overlap ───────────────────────────────────────
def main():
    log.info("🤖 AutoBot started")
    log.info(f"   YouTube  : {'✅' if UPLOAD_YOUTUBE   else '❌'}")
    log.info(f"   TikTok   : {'✅' if UPLOAD_TIKTOK    else '❌'}")
    log.info(f"   Instagram: {'✅' if UPLOAD_INSTAGRAM else '❌'}")
    log.info(f"   Facebook : {'✅' if UPLOAD_FACEBOOK  else '❌'}")
    log.info(f"   Gap      : {HOURS_BETWEEN}h between each video")

    slot = 0

    while True:
        # Run one video
        run_single_video(slot)
        slot += 1

        # Wait exactly HOURS_BETWEEN hours after this video finishes
        next_time = datetime.now() + timedelta(hours=HOURS_BETWEEN)
        wait_secs = HOURS_BETWEEN * 3600

        log.info(
            f"\n⏰ Next video (slot {slot}) at "
            f"{next_time.strftime('%Y-%m-%d %H:%M')} "
            f"— sleeping {HOURS_BETWEEN}h\n"
        )

        # Sleep in 60s chunks so Ctrl+C works cleanly
        slept = 0
        while slept < wait_secs:
            time.sleep(min(60, wait_secs - slept))
            slept += 60


if __name__ == "__main__":
    main()
