"""
tools/social_uploader.py
-------------------------
YouTube and Instagram upload clients for the Social Media Agent.

YouTube: YouTube Data API v3 with OAuth2 credentials
Instagram: Instagram Graph API with access token

Both uploads are best-effort — pipeline does not fail if uploads fail.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional


# ─── YouTube ──────────────────────────────────────────────────────────────────

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_TOKEN_FILE = "youtube_token.json"


def _get_youtube_service():
    """Build authenticated YouTube API service."""
    import json
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        with open(YOUTUBE_TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        creds = Credentials.from_authorized_user_info(token_data, YOUTUBE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = {
                "installed": {
                    "client_id": os.environ["YOUTUBE_CLIENT_ID"],
                    "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(YOUTUBE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "unlisted",
    max_retries: int = 3,
) -> Optional[str]:
    """
    Upload a video to YouTube with retry logic.

    Returns:
        YouTube video URL on success, None on failure.
    """
    from googleapiclient.http import MediaFileUpload
    import googleapiclient.errors

    for attempt in range(1, max_retries + 1):
        try:
            youtube = _get_youtube_service()
            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:500],
                    "categoryId": "27",  # Education
                },
                "status": {"privacyStatus": privacy},
            }
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True,
                chunksize=1024 * 1024,
            )
            request = youtube.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media,
            )
            response = None
            while response is None:
                _, response = request.next_chunk()

            video_id = response.get("id", "")
            url = f"https://youtu.be/{video_id}"
            print(f"  [YouTube] Uploaded: {url}")
            return url

        except googleapiclient.errors.HttpError as exc:
            wait = 2 ** attempt
            print(f"  [YouTube] Upload failed (attempt {attempt}/{max_retries}): {exc}")
            if attempt < max_retries:
                print(f"  [YouTube] Retrying in {wait}s...")
                time.sleep(wait)
        except Exception as exc:
            print(f"  [YouTube] Unexpected error: {exc}")
            break

    print(f"  [YouTube] All {max_retries} upload attempts failed. Video saved at: {video_path}")
    return None


# ─── Instagram ────────────────────────────────────────────────────────────────

def upload_to_instagram(
    video_path: str,
    caption: str,
    max_retries: int = 3,
) -> Optional[str]:
    """
    Upload a video as an Instagram Reel using the Graph API.

    Requires:
    - INSTAGRAM_ACCESS_TOKEN env var
    - INSTAGRAM_ACCOUNT_ID env var

    Returns:
        Instagram post URL on success, None on failure.
    """
    import requests

    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

    if not access_token or not account_id:
        print("  [Instagram] Skipping: INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID not set.")
        return None

    # Instagram Graph API requires a publicly accessible video URL
    # For production: upload to a CDN or use a signed URL
    # For demo: skip if no public URL available
    print("  [Instagram] NOTE: Instagram upload requires a public video URL.")
    print("  [Instagram] For production, host the video on a CDN first.")
    print(f"  [Instagram] Local video path: {video_path}")

    # Graph API upload flow (requires public URL):
    # Step 1: POST /media (create media container)
    # Step 2: POST /media_publish (publish)
    # This is a placeholder implementation
    print("  [Instagram] Upload skipped (no CDN hosting configured).")
    return None
