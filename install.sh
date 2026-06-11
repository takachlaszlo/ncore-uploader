#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

echo
echo "=== nCore Universal Uploader telepítő ==="
echo

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

if command -v playwright >/dev/null 2>&1; then
  playwright install chromium || true
fi

ask() {
  local prompt="$1"
  local default="${2:-}"
  local value=""

  if [ -n "$default" ]; then
    read -r -p "$prompt [$default]: " value
    echo "${value:-$default}"
  else
    read -r -p "$prompt: " value
    echo "$value"
  fi
}

ask_secret() {
  local prompt="$1"
  local value=""
  read -r -s -p "$prompt: " value
  echo
  echo "$value"
}

echo
TMDB_API_KEY="$(ask "TMDb API key")"
SPOTIFY_CLIENT_ID="$(ask "Spotify Client ID")"
SPOTIFY_CLIENT_SECRET="$(ask_secret "Spotify Client Secret")"
DISCOGS_TOKEN="$(ask "Discogs token")"

echo
QB_URL="$(ask "qBittorrent URL" "http://127.0.0.1:8080")"
QB_USER="$(ask "qBittorrent username")"
QB_PASS="$(ask_secret "qBittorrent password")"

echo
NCORE_UPLOAD_URL="$(ask "nCore upload URL" "https://ncore.pro/upload.php")"
NCORE_ANNOUNCE_URL="$(ask "nCore announce / tracker URL")"

echo
NCORE_UPLOAD_BASE="$(ask "Projekt útvonala" "$BASE_DIR")"
MUSIC_WATCH_DIR="$(ask "Zenei watch mappa" "$HOME/torrents/qbittorrent/music")"
QBIT_SAVE_ROOT="$(ask "qBittorrent alap mentési mappa" "$HOME/torrents/qbittorrent")"
PYTHON_BIN="$(ask "Python bináris" "$BASE_DIR/venv/bin/python")"

cat > .env <<ENV
TMDB_API_KEY=$TMDB_API_KEY
SPOTIFY_CLIENT_ID=$SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET=$SPOTIFY_CLIENT_SECRET
DISCOGS_TOKEN=$DISCOGS_TOKEN

QB_URL=$QB_URL
QB_USER=$QB_USER
QB_PASS=$QB_PASS

NCORE_UPLOAD_URL=$NCORE_UPLOAD_URL
NCORE_ANNOUNCE_URL=$NCORE_ANNOUNCE_URL

NCORE_UPLOAD_BASE=$NCORE_UPLOAD_BASE
MUSIC_WATCH_DIR=$MUSIC_WATCH_DIR
QBIT_SAVE_ROOT=$QBIT_SAVE_ROOT
PYTHON_BIN=$PYTHON_BIN
ENV

cat > config.yaml <<YAML
metadata:
  tmdb_api_key: "$TMDB_API_KEY"

spotify:
  client_id: "$SPOTIFY_CLIENT_ID"
  client_secret: "$SPOTIFY_CLIENT_SECRET"

discogs:
  token: "$DISCOGS_TOKEN"

ncore:
  upload_url: "$NCORE_UPLOAD_URL"

torrent:
  announce_url: "$NCORE_ANNOUNCE_URL"

auth:
  cookies_file: "auth/ncore.txt"

paths:
  torrent_output: "work/torrents"
  nfo_output: "work/nfo"
  techinfo_output: "work/techinfo"
  images_output: "work/images"
  screenshots_output: "work/screenshots"
  downloaded_torrents: "work/downloaded_torrents"
YAML

mkdir -p auth browser_profile work/{torrents,nfo,techinfo,images,screenshots,downloaded_torrents,upload_responses,excluded_from_ncore_upload}

chmod +x qbit_finished_music_autoupload.py batch_upload.py generate_music_batch_list.py uploader.py ncore_login.py

echo
echo "Telepítés kész."
echo
echo "qBittorrent Run external program:"
echo "$PYTHON_BIN $BASE_DIR/qbit_finished_music_autoupload.py \"%F\" \"%N\" \"%R\" \"%L\""
echo
