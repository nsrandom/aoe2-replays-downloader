#!/usr/bin/env python3
"""Download AoE2 game replays from aoe2insights.com."""

import json
import os
import sys
import tempfile
import zipfile

import requests
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
MATCH_URL = "https://www.aoe2insights.com/match/{game_id}/"
REPLAY_URL = "https://aoe.ms/replay/?gameId={game_id}&profileId={profile_id}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}


def load_config():
    """Load configuration from config.json."""
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Config file not found at {CONFIG_PATH}")
        print(f"Please create a config.json file. See config.json.example for reference.")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    if "save_dir" not in config or not config["save_dir"]:
        print("Error: 'save_dir' is required in config.json")
        print('Example: {"save_dir": "./replays", ...}')
        sys.exit(1)

    save_dir = config["save_dir"]
    # Resolve relative paths against the script directory
    if not os.path.isabs(save_dir):
        save_dir = os.path.join(SCRIPT_DIR, save_dir)

    if not os.path.isdir(save_dir):
        answer = input(f"Save directory does not exist: {save_dir}\nCreate it? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            sys.exit(1)
        os.makedirs(save_dir, exist_ok=True)
        print(f"  ✓ Created directory: {save_dir}")

    # known_profiles: {name: profileId} — lowercase the keys for matching
    known_profiles = config.get("known_profiles", {})
    known_profiles = {k.lower(): v for k, v in known_profiles.items()}

    return {
        "save_dir": save_dir,
        "known_profiles": known_profiles,
    }


def fetch_savegame_links(game_id):
    """Use Playwright to load the match page (bypassing Cloudflare) and
    extract player data from the analysis JSON to build download URLs."""
    url = MATCH_URL.format(game_id=game_id)
    print(f"Fetching match page: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            title = page.title()
            if "not found" in title.lower() or "#not found" in page.url:
                print(f"  ✗ Match {game_id} not found on aoe2insights.com.")
                return []

            # Fetch the analysis JSON from within the authenticated page context
            result = page.evaluate(
                """async (gameId) => {
                    const resp = await fetch(
                        `/media/matches/analysis/analysis-${gameId}.json`
                    );
                    if (!resp.ok) return {error: resp.status};
                    const data = await resp.json();
                    return Object.values(data.player).map(p => ({
                        name: p.name,
                        profile_id: p.profile_id,
                        type: p.type,
                    }));
                }""",
                game_id,
            )
        finally:
            browser.close()

    if isinstance(result, dict) and "error" in result:
        print(f"  ✗ Failed to fetch analysis data (HTTP {result['error']}).")
        return []

    savegames = []
    for player in result:
        if player.get("type") != "human":
            continue
        name = player.get("name", "Unknown")
        profile_id = player.get("profile_id")
        download_url = REPLAY_URL.format(
            game_id=game_id,
            profile_id=profile_id if profile_id else "",
        )
        savegames.append((name, download_url))

    return savegames


def select_pov(savegames, known_profiles):
    """Select the POV of a known profile, or the first available player."""
    # Build a set of known profile IDs for matching against download URLs
    known_ids = {str(pid) for pid in known_profiles.values() if pid}

    for player_name, download_url in savegames:
        # Match by player name
        if player_name.lower() in known_profiles:
            print(f"  ✓ Found known profile: {player_name}")
            return player_name, download_url
        # Match by profile ID in the download URL
        for name, pid in known_profiles.items():
            if pid and f"profileId={pid}" in download_url:
                print(f"  ✓ Found known profile by ID: {name} (profileId={pid})")
                return player_name, download_url

    # No known profile found — pick the first available
    player_name, download_url = savegames[0]
    print(f"  → No known profile found, using: {player_name}")
    return player_name, download_url


def download_and_extract(download_url, save_dir):
    """Download the replay zip and extract .aoe2record files."""
    print(f"Downloading replay from: {download_url}")

    resp = requests.get(download_url, headers=HEADERS, timeout=60, allow_redirects=True)
    resp.raise_for_status()

    # Save to a temp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            record_files = [n for n in zf.namelist() if n.endswith(".aoe2record")]
            if not record_files:
                print("  ✗ No .aoe2record files found in the zip archive.")
                return None

            for name in record_files:
                dest = os.path.join(save_dir, os.path.basename(name))
                with zf.open(name) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                print(f"  ✓ Extracted: {dest}")

            return dest
    finally:
        os.unlink(tmp_path)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <game-id>")
        sys.exit(1)

    game_id = sys.argv[1]
    config = load_config()

    # Step 1: Fetch savegame links
    savegames = fetch_savegame_links(game_id)
    if not savegames:
        print("No savegame downloads available for this match.")
        sys.exit(1)

    print(f"Found {len(savegames)} savegame(s):")
    for name, url in savegames:
        print(f"  • {name}: {url}")

    # Step 2: Select POV
    player_name, download_url = select_pov(savegames, config["known_profiles"])

    # Step 3: Download and extract
    print(f"\nDownloading {player_name}'s replay...")
    result = download_and_extract(download_url, config["save_dir"])

    if result:
        print(f"\nDone! Replay saved to: {result}")
    else:
        print("\nFailed to extract replay.")
        sys.exit(1)


if __name__ == "__main__":
    main()
