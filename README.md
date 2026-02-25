# AoE2 Replay Downloader

Download Age of Empires II game replays from [aoe2insights.com](https://www.aoe2insights.com) as `.aoe2record` files.

## How It Works

Given a match ID, the script:

1. **Fetches** the match page at `aoe2insights.com/match/<game-id>/`
2. **Parses** the HTML to extract download links and player names from the Savegames section
3. **Selects a POV** — if a player matches one of your `known_profiles`, their point of view is chosen; otherwise the first available player is used
4. **Downloads** the replay zip from Microsoft's replay API (`aoe.ms/replay/`)
5. **Extracts** the `.aoe2record` file into your configured save directory

## Setup

**Requirements:** Python 3.8+

```bash
# Clone the repo and set up a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Copy the example config and edit it with your settings:

```bash
cp config.json.example config.json
```

```json
{
  "save_dir": "./replays",
  "known_profiles": {
    "YourPlayerName": "12345678",
    "FriendName": "87654321"
  }
}
```

| Key | Description |
|-----|-------------|
| `save_dir` | Directory where `.aoe2record` files are saved (relative to script directory, or absolute) |
| `known_profiles` | Map of player names to profile IDs. Used to prioritize which POV to download (matched by name or ID, case-insensitive) |

## Usage

```bash
python download_replay.py <game-id>
```

The game ID can be found in the URL of any match page on aoe2insights.com:

```
https://www.aoe2insights.com/match/318498344/
                                  ^^^^^^^^^
                                  game ID
```

### Example

```
$ python download_replay.py 318498344

Fetching match page: https://www.aoe2insights.com/match/318498344/
Found 2 savegame(s):
  • zi: https://aoe.ms/replay/?gameId=318498344&profileId=15592739
  • Nice: https://aoe.ms/replay/?gameId=318498344&profileId=10071204
  → No known profile found, using: zi

Downloading zi's replay...
  ✓ Extracted: ./replays/AgeIIDE_Replay_318498344.aoe2record

Done! Replay saved to: ./replays/AgeIIDE_Replay_318498344.aoe2record
```

## Notes

- **Not all replays are available** — recorded games are hosted by Microsoft and older replays may be removed
- Each match has one replay per player (different points of view); the replay file itself contains all game data regardless of POV
