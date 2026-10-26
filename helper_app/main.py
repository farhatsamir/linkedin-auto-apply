"""
Entry point for the LinkedIn Auto Apply Helper App.

Invoked via the custom protocol handler:
  linkedinautoapply://connect?token=<connect-token>

Flow:
  1. Safely parse the connect-token out of the protocol URL (never trust
     or execute any part of the raw argument - see argument-injection
     note in the architecture review).
  2. Launch a real local Chromium browser and let the user log into
     LinkedIn normally (linkedin_capture.py - unchanged, proven logic).
  3. POST the captured storage_state to the backend, authenticated by
     the one-time connect-token (not a JWT - the helper never handles
     the user's real credentials).
"""
import sys
import os
import json
import traceback
from urllib.parse import urlparse, parse_qs

import httpx  # type: ignore


# When running as a PyInstaller-bundled .exe, tell Playwright to use the
# Chromium binary bundled inside the app folder, instead of the normal
# ms-playwright cache location. In normal dev (python main.py), this has
# no effect - Playwright uses its default cache path as always.
if getattr(sys, "frozen", False):
    bundled_browser_path = os.path.join(sys._MEIPASS, "ms-playwright")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browser_path

from linkedin_capture import capture_linkedin_session

BACKEND_URL = "http://127.0.0.1:8000"  # local dev default; overridden for production builds

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper_app_log.txt")


def log(message: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(message)


def extract_token(raw_arg: str) -> str | None:
    """
    Safely extracts the 'token' query parameter from the protocol URL.
    Never executes or interprets the raw string in any other way.
    """
    try:
        parsed = urlparse(raw_arg)
        if parsed.scheme != "linkedinautoapply":
            return None
        query = parse_qs(parsed.query)
        token_values = query.get("token")
        if not token_values:
            return None
        return token_values[0]
    except Exception:
        return None


def upload_session(token: str, storage_state: dict) -> bool:
    """
    Sends the captured storage_state to the backend, authenticated by
    the one-time connect-token.
    """
    try:
        response = httpx.post(
            f"{BACKEND_URL}/linkedin-session/connect/complete",
            json={"token": token, "storage_state": storage_state},
            timeout=30,
        )
        return response.status_code == 200
    except Exception as e:
        log(f"[error] Failed to reach backend: {e}")
        return False


def main():
    log(f"[info] Launched with args: {sys.argv}")

    if len(sys.argv) < 2:
        log("[error] No protocol argument received.")
        sys.exit(1)

    raw_arg = sys.argv[1]
    token = extract_token(raw_arg)

    if not token:
        log("[error] Could not extract a valid token from the launch argument.")
        sys.exit(1)

    log("[info] Starting LinkedIn login capture...")
    try:
        storage_state = capture_linkedin_session()
    except TimeoutError:
        log("[error] Login was not completed in time.")
        sys.exit(1)

    log("[info] Login captured. Uploading to backend...")
    success = upload_session(token, storage_state)

    if success:
        log("[success] LinkedIn connected successfully.")
    else:
        log("[error] Failed to save session to backend.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("[fatal] Unhandled exception:")
        log(traceback.format_exc())
    finally:
        input("\nPress Enter to close this window...")