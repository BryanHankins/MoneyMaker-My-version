"""
trends.py — Multi-source Health/Body Facts trending topic finder
Sources: YouTube, Guardian, NewsAPI, WikiMedia, Imgur, Google Trends, NASA, Evergreen
Reddit removed — returns 403 errors
"""

import os
import re
import time
import random
import logging
import json
import requests
from pathlib import Path
from datetime import datetime, date
from typing import List

log = logging.getLogger("autobot.trends")

NICHE = os.getenv("CONTENT_NICHE", "health")

# ── Health keyword filter ─────────────────────────────────────────────────────
HEALTH_KEYWORDS = [
    # Body systems
    "brain", "heart", "lung", "liver", "kidney", "stomach", "blood", "bone",
    "muscle", "nerve", "skin", "eye", "ear", "nose", "throat", "spine",
    "intestine", "gut", "cell", "dna", "gene", "chromosome", "immune",
    "hormone", "neuron", "cortex", "hippocampus", "synapse", "artery", "vein",
    "lymph", "plasma", "platelet", "cortisol", "adrenaline", "dopamine",
    "serotonin", "melatonin", "insulin", "cholesterol", "oxygen", "carbon dioxide",
    # Health topics
    "health", "body", "human", "medical", "medicine", "disease", "virus",
    "bacteria", "infection", "immune", "cancer", "diabetes", "obesity",
    "sleep", "diet", "nutrition", "vitamin", "supplement", "exercise",
    "fitness", "metabolism", "calorie", "protein", "fat", "carb",
    "mental", "anxiety", "depression", "stress", "memory", "cognition",
    "aging", "longevity", "lifespan", "inflammation", "pain", "healing",
    # Body facts triggers
    "twitch", "yawn", "blink", "sneeze", "cough", "breathe", "sweat",
    "digest", "absorb", "burn", "regenerate", "grow", "repair",
    "goosebump", "reflex", "dream", "unconscious", "conscious",
    # Science/research
    "study", "research", "scientists", "discovered", "found", "evidence",
    "clinical", "trial", "experiment", "biology", "anatomy", "physiology",
    "neuroscience", "psychology", "psychiatry", "surgery", "therapy",
]

# ── Skip patterns ─────────────────────────────────────────────────────────────
SKIP_PATTERNS = [
    r"\bpolitics?\b", r"\belection\b", r"\bcrypto\b", r"\bbitcoin\b",
    r"\bstock market\b", r"\bcelebrity\b", r"\bsoftware\b", r"\bwindows\b",
    r"\bmicrosoft\b", r"\bgaming\b", r"\bfootball\b", r"\bbasketball\b",
    r"\bsoccer\b", r"\beconomy\b", r"\bpolitician\b", r"\bwar\b",
    r"\belection\b", r"\bpresident\b", r"\bcongress\b", r"\bsenate\b",
    r"\brecall\b", r"\blawsuit\b", r"\bcourt\b", r"\bjudge\b",
]

# ── Health/Body Facts Subreddits ──────────────────────────────────────────────
HEALTH_SUBREDDITS = [
    "todayilearned",
    "interestingasfuck",
    "Damnthatsinteresting",
    "science",
    "mildlyinteresting",
    "woahdude",
    "biology",
    "neuroscience",
    "medicine",
    "medical",
    "askscience",
    "everythingscience",
    "longevity",
    "sleep",
    "nutrition",
    "microbiology",
    "psychology",
    "anatomy",
    "bodybuilding",
    "Health",
]

# ── Large evergreen health/body facts pool ────────────────────────────────────
EVERGREEN = [
    "Your brain generates enough electricity to power a small light bulb",
    "You produce enough saliva in your lifetime to fill two swimming pools",
    "Your stomach acid is strong enough to dissolve razor blades",
    "The human eye can distinguish about 10 million different colors",
    "Your body produces 300 billion new cells every single day",
    "The human nose can detect over 1 trillion different scents",
    "Your heart beats about 100,000 times per day — 3 billion times in a lifetime",
    "You lose about 30,000 to 40,000 dead skin cells every hour",
    "The human brain is 73 percent water — losing just 2 percent causes memory problems",
    "Your liver can regenerate itself completely from just 25 percent of its original tissue",
    "The cornea is the only tissue in the human body with no blood vessels",
    "You twitch when falling asleep because your brain thinks you are dying",
    "Goosebumps are completely useless in humans — they evolved to make our ancestors look bigger",
    "Your pupils dilate up to 45 percent when you look at someone you love",
    "The acid in your stomach is replaced completely every 4 days",
    "You cannot breathe and swallow at the same time — your body physically prevents it",
    "The human skeleton is stronger than concrete by weight",
    "Your small intestine is about 6 meters long despite being called small",
    "Babies are born with 270 bones but adults only have 206 — bones fuse as you grow",
    "The strongest muscle in your body relative to its size is the masseter in your jaw",
    "Your body contains enough carbon to make 900 pencils",
    "The human bladder can stretch to hold up to 500ml of liquid",
    "You have more bacteria in your gut than cells in your entire body",
    "Cold water doesn't actually help a burn — it can make the damage worse",
    "Sitting for 8 hours a day increases your risk of death as much as smoking",
    "Your brain is more active at night while you sleep than during the day",
    "The appendix is not useless — it stores good bacteria to repopulate your gut after illness",
    "Humans are the only animals that cry emotional tears",
    "Your nose and sinuses produce about a litre of mucus every single day",
    "Reading in dim light doesn't damage your eyes — it just strains them temporarily",
    "You blink about 15 to 20 times per minute but almost never while reading",
    "The human body has more than 37 trillion cells",
    "Your fingernails grow faster on your dominant hand",
    "The skin is the largest organ in the body — it weighs about 4kg",
    "Yawning actually cools your brain down rather than signalling tiredness",
    "Humans shed their entire outer layer of skin every 2 to 4 weeks",
    "Your bones are constantly being broken down and rebuilt — you have a new skeleton every 10 years",
    "The average person has about 70,000 thoughts per day",
    "Stress physically shrinks your brain — the hippocampus gets smaller under chronic stress",
    "The acid in your stomach is so strong it would burn a hole in your carpet",
    "Humans are the only species that can consciously hold their breath",
    "Your taste buds completely replace themselves every 10 to 14 days",
    "The human body glows — we emit light that is 1000 times too faint for the eye to detect",
    "You lose half your taste buds by the time you are 60",
    "Laughing 100 times burns as many calories as 10 minutes on a rowing machine",
    "Your blood vessels would circle Earth 2.5 times if laid end to end",
    "The human immune system destroys thousands of cancer cells in your body every single day",
    "Chronic sleep deprivation causes the brain to eat itself — literally",
    "Your body produces its own natural painkillers called endorphins that are 200 times stronger than morphine",
    "Your heart has its own nervous system and can beat outside of your body",
    "The average human produces enough heat in 30 minutes to boil half a litre of water",
    "Your eyes contain 120 million rod cells that allow you to see in near total darkness",
    "The human jaw can exert up to 200 pounds of force per square inch",
    "Bone is 5 times stronger than steel of the same weight",
    "Your brain uses 20 percent of your body's total energy despite being only 2 percent of its weight",
    "The human body contains about 60,000 miles of blood vessels",
    "Your ears never stop working — even when you sleep your brain filters out sounds",
    "The average person walks about 100,000 miles in their lifetime — 4 times around the Earth",
    "Your body replaces every atom it is made of over the course of about 7 years",
    "The human brain can process images seen for as little as 13 milliseconds",
    "Your nose is directly connected to your memory — smell bypasses the thalamus entirely",
    "The human body contains enough fat to make 7 bars of soap",
    "Your immune system remembers every pathogen it has ever defeated",
    "The human eye moves about 100,000 times a day — equivalent to walking 50 miles",
    "Your hair grows faster when you are asleep than when you are awake",
    "Teeth are the only part of the human body that cannot repair themselves",
    "The human brain shrinks by 1 percent every decade after age 40",
    "Your sweat glands can produce up to 10 litres of sweat per day in extreme heat",
    "The surface area of your lungs is roughly the size of a tennis court",
    "Your body makes about 2 million red blood cells every second",
    "Muscle is three times more efficient than a car engine at converting fuel to motion",
    "The human body contains about 5 litres of blood which circulates completely every 60 seconds",
    "Your brain gets smaller every time you drink alcohol — but the damage is mostly reversible",
    "The human stomach can expand to hold up to 4 litres of food and liquid",
    "Your vocal cords vibrate between 100 and 1000 times per second when you speak",
    "The average person produces enough dead skin cells in their lifetime to fill a skip",
    "Your immune system creates 100 billion new cells a day to fight off invaders",
]


# ── Helper functions ──────────────────────────────────────────────────────────

def _is_health_topic(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in HEALTH_KEYWORDS)


def _is_bad_topic(title: str) -> bool:
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False


def _clean_title(title: str) -> str:
    for prefix in [r"^TIL\s+that\s+", r"^TIL\s+", r"^Today I Learned\s+that\s+", r"^Today I Learned\s+"]:
        title = re.sub(prefix, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+[-–|]\s+\w[\w\s]+$", "", title).strip()
    if title:
        title = title[0].upper() + title[1:]
    return title


def load_used_topics() -> list:
    history_file = Path("logs/used_topics.json")
    if history_file.exists():
        try:
            return json.loads(history_file.read_text())
        except Exception:
            return []
    return []


def save_used_topic(topic: str):
    history = load_used_topics()
    history.append({"topic": topic, "date": str(datetime.now())})
    Path("logs").mkdir(exist_ok=True)
    Path("logs/used_topics.json").write_text(json.dumps(history, indent=2))


# ── Source 1: YouTube Trending — Science & Tech (cat 28) ─────────────────────
def _get_youtube_trending() -> List[str]:
    try:
        youtube_key = os.getenv("YOUTUBE_API_KEY", "")
        if not youtube_key:
            log.warning("YOUTUBE_API_KEY not set — skipping YouTube trending")
            return []

        topics = []
        # Search category 28 (Science & Technology) and 26 (Howto & Style) for health
        for cat_id in ["28", "26", "27"]:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet",
                    "chart": "mostPopular",
                    "regionCode": "US",
                    "videoCategoryId": cat_id,
                    "maxResults": 20,
                    "key": youtube_key,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            titles = [v["snippet"]["title"] for v in resp.json().get("items", [])]
            cleaned = [_clean_title(t) for t in titles]
            health = [t for t in cleaned if _is_health_topic(t) and not _is_bad_topic(t) and 20 <= len(t) <= 150]
            topics.extend(health)

        log.info(f"YouTube trending: {len(topics)} health topics")
        return topics
    except Exception as e:
        log.warning(f"YouTube trending failed: {e}")
        return []


# ── Source 2: Guardian — Health Section ───────────────────────────────────────
def _get_guardian_topics() -> List[str]:
    try:
        key = os.getenv("GUARDIAN_API_KEY", "test")
        resp = requests.get(
            "https://content.guardianapis.com/search",
            params={
                "section": "science",
                "tag": "science/health",
                "order-by": "newest",
                "page-size": 30,
                "api-key": key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            # Try health section directly
            resp = requests.get(
                "https://content.guardianapis.com/search",
                params={
                    "q": "human body OR brain OR health",
                    "order-by": "relevance",
                    "page-size": 20,
                    "api-key": key,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []

        results = resp.json().get("response", {}).get("results", [])
        topics = []
        for r in results:
            title = _clean_title(r.get("webTitle", ""))
            if _is_health_topic(title) and not _is_bad_topic(title) and 20 <= len(title) <= 150:
                topics.append(title)

        log.info(f"Guardian: {len(topics)} health topics")
        return topics
    except Exception as e:
        log.warning(f"Guardian failed: {e}")
        return []


# ── Source 3: NewsAPI — Health/Medical News ───────────────────────────────────
def _get_news_topics() -> List[str]:
    try:
        key = os.getenv("NEWS_API_KEY", "")
        if not key:
            log.warning("NEWS_API_KEY not set — skipping NewsAPI")
            return []

        topics = []
        for query in ["human body discovery", "brain health", "medical breakthrough", "body science"]:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "popularity",
                    "pageSize": 10,
                    "apiKey": key,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                for a in articles:
                    title = _clean_title(a.get("title", ""))
                    if _is_health_topic(title) and not _is_bad_topic(title) and 20 <= len(title) <= 150:
                        topics.append(title)
            time.sleep(0.5)

        log.info(f"NewsAPI: {len(topics)} health topics")
        return topics
    except Exception as e:
        log.warning(f"NewsAPI failed: {e}")
        return []


# ── Source 4: WikiMedia Trending Articles ─────────────────────────────────────
def _get_wikimedia_trending() -> List[str]:
    try:
        today = date.today()
        url = (
            f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
            f"en.wikipedia/all-access/{today.year}/{today.month:02d}/{today.day:02d}"
        )
        resp = requests.get(url, timeout=10, headers={"User-Agent": "HealthFactsBot/1.0"})
        if resp.status_code != 200:
            log.warning(f"WikiMedia API error: {resp.status_code}")
            return []

        articles = resp.json().get("items", [{}])[0].get("articles", [])
        titles = [a["article"].replace("_", " ") for a in articles[:100]]

        skip = ["main page", "special:", "wikipedia:", "portal:", "file:"]
        topics = []
        for t in titles:
            if any(s in t.lower() for s in skip):
                continue
            if _is_health_topic(t) and not _is_bad_topic(t) and 10 <= len(t) <= 100:
                clean = f"Fascinating facts about {t}"
                topics.append(clean)

        log.info(f"WikiMedia trending: {len(topics)} health topics")
        return topics[:10]
    except Exception as e:
        log.warning(f"WikiMedia trending failed: {e}")
        return []


# ── Source 5: NIH News in Health RSS ─────────────────────────────────────────
def _get_nih_topics() -> List[str]:
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get(
            "https://newsinhealth.nih.gov/rss/",
            timeout=10,
            headers={"User-Agent": "HealthFactsBot/1.0"},
        )
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        topics = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            title = _clean_title(title)
            if _is_health_topic(title) and not _is_bad_topic(title) and 20 <= len(title) <= 150:
                topics.append(title)

        log.info(f"NIH: {len(topics)} health topics")
        return topics
    except Exception as e:
        log.warning(f"NIH RSS failed: {e}")
        return []


# ── Source 6: Medical News Today RSS ─────────────────────────────────────────
def _get_medical_news_topics() -> List[str]:
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get(
            "https://www.medicalnewstoday.com/rss",
            timeout=10,
            headers={"User-Agent": "HealthFactsBot/1.0"},
        )
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        topics = []
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            title = _clean_title(title)
            if _is_health_topic(title) and not _is_bad_topic(title) and 20 <= len(title) <= 150:
                topics.append(title)

        log.info(f"Medical News Today: {len(topics)} topics")
        return topics[:10]
    except Exception as e:
        log.warning(f"Medical News Today RSS failed: {e}")
        return []


# ── Source 7: Google Trends ───────────────────────────────────────────────────
def _get_google_trends() -> List[str]:
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        df = pytrends.trending_searches(pn="united_states")
        topics = df[0].tolist()
        health_topics = [t for t in topics if _is_health_topic(t) and not _is_bad_topic(t)]
        log.info(f"Google Trends: {len(health_topics)} health topics")
        return health_topics
    except Exception as e:
        log.warning(f"Google Trends failed: {e}")
        return []


# ── Source 8: Imgur Viral Feed ────────────────────────────────────────────────
def _get_imgur_trending() -> List[str]:
    try:
        resp = requests.get(
            "https://api.imgur.com/3/gallery/hot/viral/0.json",
            headers={
                "Authorization": "Client-ID c5c5e28c18c5855",
                "User-Agent": "HealthFactsBot/1.0",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []

        items = resp.json().get("data", [])
        topics = []
        for item in items:
            title = _clean_title(item.get("title", ""))
            if _is_health_topic(title) and not _is_bad_topic(title) and 20 <= len(title) <= 150:
                topics.append(title)

        log.info(f"Imgur: {len(topics)} health topics")
        return topics[:10]
    except Exception as e:
        log.warning(f"Imgur trending failed: {e}")
        return []


# ── Main topic fetcher ────────────────────────────────────────────────────────
def get_trending_topics(count: int = 1) -> List[str]:
    log.info(f"Fetching trending topics (niche='{NICHE}', count={count})")

    used = {u["topic"].lower() for u in load_used_topics()}

    all_topics = []

    sources = [
        ("YouTube",          _get_youtube_trending),
        ("Guardian",         _get_guardian_topics),
        ("NIH",              _get_nih_topics),
        ("Medical News",     _get_medical_news_topics),
        ("NewsAPI",          _get_news_topics),
        ("WikiMedia",        _get_wikimedia_trending),
        ("Imgur",            _get_imgur_trending),
        ("Google Trends",    _get_google_trends),
    ]

    for source_name, source_fn in sources:
        try:
            results = source_fn()
            if results:
                log.info(f"✅ {source_name}: {len(results)} topics")
                all_topics.extend(results)
        except Exception as e:
            log.warning(f"Source {source_name} failed: {e}")

    # Deduplicate and filter used
    seen, unique = set(), []
    for t in all_topics:
        key = t.lower().strip()
        if key not in seen and key not in used and 20 <= len(t) <= 150:
            seen.add(key)
            unique.append(t)

    log.info(f"Total unique fresh topics: {len(unique)}")

    if len(unique) >= count:
        selected = unique[:count]
        for t in selected:
            save_used_topic(t)
        log.info(f"Topics selected: {selected}")
        return selected

    # Fall back to evergreen health facts
    log.warning("Not enough live topics — using evergreen fallbacks")
    unused_evergreen = [t for t in EVERGREEN if t.lower() not in used]
    if not unused_evergreen:
        unused_evergreen = EVERGREEN
        log.info("All evergreen topics used — resetting cycle")

    needed  = count - len(unique)
    padding = random.sample(unused_evergreen, min(needed, len(unused_evergreen)))
    result  = (unique + padding)[:count]

    for t in result:
        save_used_topic(t)

    log.info(f"Final topics: {result}")
    return result