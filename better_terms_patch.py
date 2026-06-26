"""
PATCH v2: Better video clip relevance for MoneyPrinterTurbo
============================================================
Drop this into MoneyPrinterTurbo-main folder and run once.
Fixed: no regex escape errors on Windows Python 3.12.

Run with:
    python better_terms_patch_v2.py

Then restart the WebUI.
"""

import re
import json
import shutil
from pathlib import Path

LLM_PATH = Path("app/services/llm.py")

NEW_FUNC = """\
def generate_terms(
    video_subject: str,
    video_script: str,
    amount: int = 5,
    language: str = None,
) -> List[str]:
    \"\"\"
    Generate scene-specific search terms — each one describes a visual moment
    in the script rather than just the overall topic.
    \"\"\"
    logger.info(f"generate_terms - subject: {video_subject}")

    sentences = [s.strip() for s in video_script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not sentences:
        sentences = [video_subject]

    amount = max(1, min(amount, len(sentences) * 2))

    numbered_lines = ""
    for i, s in enumerate(sentences[:amount]):
        numbered_lines += f"{i+1}. {s}\\n"

    amount_str = str(amount)

    prompt = (
        "You are a professional video editor choosing stock footage for a short-form video.\\n\\n"
        "VIDEO TOPIC: " + video_subject + "\\n\\n"
        "VIDEO SCRIPT SEGMENTS:\\n" + numbered_lines + "\\n"
        "YOUR TASK:\\n"
        "For each segment above write ONE Pexels/Pixabay search query (3-6 words) "
        "describing the most visually relevant stock footage clip for that moment.\\n\\n"
        "RULES:\\n"
        "1. Queries MUST be in English regardless of script language.\\n"
        "2. Use concrete nouns and action verbs. No abstract words like success, concept, idea.\\n"
        "3. Think like a cinematographer: describe what the CAMERA would see.\\n"
        "4. Return ONLY a JSON array of " + amount_str + " strings, no explanation, no markdown.\\n\\n"
        "GOOD example: [\\"golden retriever catching frisbee park\\", \\"close up dog paws running grass\\"]\\n"
        "BAD example:  [\\"dog\\", \\"happiness\\", \\"pet ownership\\"]\\n\\n"
        "Return only the JSON array:"
    )

    response = ""
    try:
        response = _generate_response(prompt=prompt)
        cleaned = response.strip()

        # Strip markdown fences if present
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                if "[" in part:
                    cleaned = part.strip()
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                    break

        # Extract JSON array
        start = cleaned.find("[")
        end   = cleaned.rfind("]") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON array found in response")

        terms = json.loads(cleaned[start:end])
        if not isinstance(terms, list):
            raise ValueError(f"Expected list, got {type(terms)}")

        # Deduplicate while preserving order
        seen = set()
        clean_terms = []
        for t in terms:
            t = str(t).strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                clean_terms.append(t)

        if not clean_terms:
            raise ValueError("Empty terms after cleaning")

        logger.success(f"generate_terms success: {clean_terms}")
        return clean_terms

    except Exception as e:
        logger.error(f"generate_terms failed: {e} | response was: {response!r}")
        fallback = [video_subject] * amount
        logger.warning(f"Falling back to: {fallback}")
        return fallback

"""


def patch():
    if not LLM_PATH.exists():
        print(f"ERROR: {LLM_PATH} not found.")
        print("Make sure you run this from the MoneyPrinterTurbo-main folder.")
        return False

    # Back up original
    backup = LLM_PATH.with_suffix(".py.bak")
    shutil.copy2(LLM_PATH, backup)
    print(f"Backed up original to {backup}")

    source = LLM_PATH.read_text(encoding="utf-8")

    # Ensure required imports exist
    added = []
    if "import json" not in source:
        source = "import json\n" + source
        added.append("import json")
    if added:
        print(f"Added imports: {', '.join(added)}")

    # Find the generate_terms function start
    for marker in ["\ndef generate_terms(", "\nasync def generate_terms("]:
        if marker in source:
            func_start = source.index(marker) + 1
            break
    else:
        print("ERROR: Could not find generate_terms function in llm.py")
        return False

    # Find where the function ends (next top-level def)
    rest = source[func_start + 10:]
    next_def = re.search(r'\ndef [a-zA-Z_]', rest)
    if next_def:
        func_end = func_start + 10 + next_def.start() + 1
    else:
        func_end = len(source)

    # Splice in the new function
    patched = source[:func_start] + NEW_FUNC + source[func_end:]
    LLM_PATH.write_text(patched, encoding="utf-8")

    print(f"Patched {LLM_PATH} successfully!")
    print("")
    print("Changes made:")
    print("  - Terms are now scene-specific 3-6 word visual descriptions")
    print("  - Each term maps to a specific script segment")
    print("  - No more generic one-word topic keywords")
    print("  - Graceful fallback if LLM returns bad format")
    print("")
    print("Restart the WebUI and generate a video to see the improvement.")
    return True


if __name__ == "__main__":
    success = patch()
    if not success:
        exit(1)