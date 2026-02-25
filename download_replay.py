#!/usr/bin/env python3
"""Download AoE2 game replays from aoe2insights.com."""

import json
import os
import sys
import tempfile
import zipfile

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
MATCH_URL = "https://www.aoe2insights.com/match/{game_id}/"


def load_config():
    """Load configuration from config.json."""
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    save_dir = config.get("save_dir", "./replays")
    # Resolve relative paths against the script directory
    if not os.path.isabs(save_dir):
        save_dir = os.path.join(SCRIPT_DIR, save_dir)

    return {
        "save_dir": save_dir,
        "known_profiles": [p.lower() for p in config.get("known_profiles", [])],
    }


def fetch_savegame_links(game_id):
    """Fetch the match page and extract (player_name, download_url) pairs."""
    url = MATCH_URL.format(game_id=game_id)
    print(f"Fetching match page: {url}")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    savegames = []
    for li in soup.select("li.list-group-item"):
        link = li.find("a", href=lambda h: h and "aoe.ms/replay" in h)
        if not link:
            continue

        download_url = link["href"]
        # Remove the download link and color-slot span before extracting text
        # so we get clean player name from "<name>'s Point of View"
        li_copy = BeautifulSoup(str(li), "html.parser")
        for tag in li_copy.find_all(["a", "span"]):
            tag.decompose()
        text = li_copy.get_text(strip=True)

        if "'s Point of View" in text:
            player_name = text.split("'s Point of View")[0].strip()
        else:
            player_name = "Unknown"

        savegames.append((player_name, download_url))

    return savegames


def select_pov(savegames, known_profiles):
    """Select the POV of a known profile, or the first available player."""
    for player_name, download_url in savegames:
        if player_name.lower() in known_profiles:
            print(f"  ✓ Found known profile: {player_name}")
            return player_name, download_url

    # No known profile found — pick the first available
    player_name, download_url = savegames[0]
    print(f"  → No known profile found, using: {player_name}")
    return player_name, download_url


def download_and_extract(download_url, save_dir):
    """Download the replay zip and extract .aoe2record files."""
    print(f"Downloading replay from: {download_url}")

    resp = requests.get(download_url, timeout=60, allow_redirects=True)
    resp.raise_for_status()

    # Save to a temp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        os.makedirs(save_dir, exist_ok=True)

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
