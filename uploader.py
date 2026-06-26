"""
uploader.py — Upload videos to YouTube Shorts, TikTok, Instagram, Facebook
===========================================================================
Each platform has its own uploader class. Enable platforms via .env flags.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger("autobot.uploader")


def upload_to_all_platforms(
    video_path: Path,
    title: str,
    description: str,
    topic: str,
) -> Dict[str, Any]:
    """Upload to all enabled platforms. Returns dict of results per platform."""

    results = {}

    if os.getenv("UPLOAD_YOUTUBE", "false").lower() == "true":
        results["youtube"] = YouTubeUploader().upload(video_path, title, description)

    if os.getenv("UPLOAD_TIKTOK", "false").lower() == "true":
        results["tiktok"] = TikTokUploader().upload(video_path, title, description)

    if os.getenv("UPLOAD_INSTAGRAM", "false").lower() == "true":
        results["instagram"] = InstagramUploader().upload(video_path, title, description)

    if os.getenv("UPLOAD_FACEBOOK", "false").lower() == "true":
        results["facebook"] = FacebookUploader().upload(video_path, title, description)

    if not results:
        log.warning("⚠️  No upload platforms enabled. Set UPLOAD_* = true in .env")

    return results


# ── YouTube Shorts ────────────────────────────────────────────────────────────

class YouTubeUploader:
    """
    Uses the YouTube Data API v3.
    Requires: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
    Get credentials: https://console.cloud.google.com → APIs → YouTube Data API v3
    """

    def upload(self, video_path: Path, title: str, description: str) -> Dict:
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            creds = Credentials(
                token=None,
                refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
                client_id=os.getenv("YOUTUBE_CLIENT_ID"),
                client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
                token_uri="https://oauth2.googleapis.com/token",
            )

            youtube = build("youtube", "v3", credentials=creds)

            request_body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": ["shorts", "viral", "facts", "didyouknow"],
                    "categoryId": "22",   # People & Blogs
                },
                "status": {
                    "privacyStatus": os.getenv("YOUTUBE_PRIVACY", "public"),
                    "selfDeclaredMadeForKids": False,
                },
            }

            media = MediaFileUpload(
                str(video_path),
                chunksize=1024 * 1024,
                resumable=True,
                mimetype="video/mp4",
            )

            response = youtube.videos().insert(
                part="snippet,status",
                body=request_body,
                media_body=media,
            ).execute()

            video_id = response["id"]
            url = f"https://youtube.com/shorts/{video_id}"
            log.info(f"  ✅ YouTube: {url}")
            return {"success": True, "url": url, "id": video_id}

        except ImportError:
            return {"success": False, "error": "Run: pip install google-api-python-client google-auth"}
        except Exception as e:
            log.error(f"  ❌ YouTube upload failed: {e}")
            return {"success": False, "error": str(e)}


# ── TikTok ────────────────────────────────────────────────────────────────────

class TikTokUploader:
    """
    Uses TikTok Content Posting API v2 (Direct Post).
    Requires: TIKTOK_ACCESS_TOKEN
    Get token: https://developers.tiktok.com → Content Posting API
    Note: Requires TikTok for Developers account + app approval.
    """

    def upload(self, video_path: Path, title: str, description: str) -> Dict:
        try:
            import requests

            access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
            if not access_token:
                return {"success": False, "error": "TIKTOK_ACCESS_TOKEN not set"}

            file_size = video_path.stat().st_size

            # Step 1: Init upload
            init_resp = requests.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                json={
                    "post_info": {
                        "title": title[:150],
                        "privacy_level": os.getenv("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE"),
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                        "video_cover_timestamp_ms": 1000,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": file_size,
                        "chunk_size": file_size,
                        "total_chunk_count": 1,
                    },
                },
            )
            init_resp.raise_for_status()
            init_data = init_resp.json()["data"]
            publish_id  = init_data["publish_id"]
            upload_url  = init_data["upload_url"]

            # Step 2: Upload video bytes
            with open(video_path, "rb") as f:
                video_data = f.read()

            upload_resp = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                    "Content-Type": "video/mp4",
                },
                data=video_data,
                timeout=120,
            )
            upload_resp.raise_for_status()

            log.info(f"  ✅ TikTok: publish_id={publish_id} (processing)")
            return {"success": True, "publish_id": publish_id}

        except Exception as e:
            log.error(f"  ❌ TikTok upload failed: {e}")
            return {"success": False, "error": str(e)}


# ── Instagram Reels ───────────────────────────────────────────────────────────

class InstagramUploader:
    def upload(self, video_path: Path, title: str, description: str) -> Dict:
        try:
            import requests

            token      = os.getenv("INSTAGRAM_ACCESS_TOKEN")
            account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")

            if not token or not account_id:
                return {"success": False, "error": "Credentials not set"}

            video_url = _get_public_video_url(video_path)
            if not video_url:
                return {"success": False, "error": "Could not get public URL"}

            caption = f"{description[:2200]}"

            # Use new Instagram Business API endpoint
            container_resp = requests.post(
                f"https://graph.instagram.com/v21.0/{account_id}/media",
                params={
                    "media_type": "REELS",
                    "video_url":  video_url,
                    "caption":    caption,
                    "share_to_feed": "true",
                    "access_token": token,
                },
                timeout=30,
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]

            import time
            for _ in range(12):
                time.sleep(10)
                status_resp = requests.get(
                    f"https://graph.instagram.com/v21.0/{container_id}",
                    params={"fields": "status_code", "access_token": token},
                )
                status = status_resp.json().get("status_code", "")
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    return {"success": False, "error": "Media container processing failed"}

            publish_resp = requests.post(
                f"https://graph.instagram.com/v21.0/{account_id}/media_publish",
                params={"creation_id": container_id, "access_token": token},
                timeout=30,
            )
            publish_resp.raise_for_status()
            media_id = publish_resp.json()["id"]

            log.info(f"  ✅ Instagram Reel published: {media_id}")
            return {"success": True, "media_id": media_id}

        except Exception as e:
            log.error(f"  ❌ Instagram upload failed: {e}")
            return {"success": False, "error": str(e)}

# ── Facebook Reels ────────────────────────────────────────────────────────────

class FacebookUploader:
    def upload(self, video_path: Path, title: str, description: str) -> Dict:
        try:
            import requests

            token   = os.getenv("FACEBOOK_ACCESS_TOKEN")
            page_id = os.getenv("FACEBOOK_PAGE_ID")

            if not token or not page_id:
                return {"success": False, "error": "FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID not set"}

            # Get public URL via Cloudinary
            video_url = _get_public_video_url(video_path)
            if not video_url:
                return {"success": False, "error": "Could not get public URL"}

            # Use video upload endpoint instead of video_reels
            resp = requests.post(
                f"https://graph.facebook.com/v19.0/{page_id}/videos",
                params={
                    "file_url": video_url,
                    "description": f"{title}\n\n{description[:5000]}",
                    "published": "true",
                    "access_token": token,
                },
                timeout=60,
            )
            resp.raise_for_status()
            video_id = resp.json().get("id")
            log.info(f"  ✅ Facebook video published: {video_id}")
            return {"success": True, "video_id": video_id}

        except Exception as e:
            log.error(f"  ❌ Facebook upload failed: {e}")
            return {"success": False, "error": str(e)}
    def upload(self, video_path: Path, title: str, description: str) -> Dict:
        try:
            import requests

            token   = os.getenv("FACEBOOK_ACCESS_TOKEN")
            page_id = os.getenv("FACEBOOK_PAGE_ID")

            if not token or not page_id:
                return {"success": False, "error": "FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID not set"}

            # Get public URL via Cloudinary
            video_url = _get_public_video_url(video_path)
            if not video_url:
                return {"success": False, "error": "Could not get public URL"}

            # Use video upload endpoint instead of video_reels
            resp = requests.post(
                f"https://graph.facebook.com/v19.0/{page_id}/videos",
                params={
                    "file_url": video_url,
                    "description": f"{title}\n\n{description[:5000]}",
                    "published": "true",
                    "access_token": token,
                },
                timeout=60,
            )
            resp.raise_for_status()
            video_id = resp.json().get("id")
            log.info(f"  ✅ Facebook video published: {video_id}")
            return {"success": True, "video_id": video_id}

        except Exception as e:
            log.error(f"  ❌ Facebook upload failed: {e}")
            return {"success": False, "error": str(e)}
# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_public_video_url(video_path: Path) -> str:
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        )

        result = cloudinary.uploader.upload_large(
            str(video_path),
            resource_type="video",
            folder="autobot",
        )
        url = result.get("secure_url", "")
        log.info(f"Video uploaded to Cloudinary: {url}")
        return url

    except Exception as e:
        log.error(f"Cloudinary upload error: {e}")
        return ""