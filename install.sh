#!/usr/bin/env bash
set -e

echo
echo "=== nCore Universal Uploader telepítő ==="
echo

python3 -m venv venv

source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

playwright install chromium

echo
echo "TMDb API key:"
read TMDB

echo
echo "Spotify Client ID:"
read SPOTIFY_ID

echo
echo "Spotify Client Secret:"
read SPOTIFY_SECRET

echo
echo "Discogs token:"
read DISCOGS

echo
echo "nCore announce URL / tracker URL:"
read ANNOUNCE_URL

echo
echo "qBittorrent URL (pl. http://127.0.0.1:8080):"
read QB_URL

echo
echo "qBittorrent username:"
read QB_USER

echo
echo "qBittorrent password:"
read -s QB_PASS
echo

cat > .env <<ENV
TMDB_API_KEY=$TMDB
SPOTIFY_CLIENT_ID=$SPOTIFY_ID
SPOTIFY_CLIENT_SECRET=$SPOTIFY_SECRET
DISCOGS_TOKEN=$DISCOGS
QB_URL=$QB_URL
QB_USER=$QB_USER
QB_PASS=$QB_PASS
ENV

cp config.example.yaml config.yaml

sed -i "s|tmdb_api_key: \"\"|tmdb_api_key: \"$TMDB\"|g" config.yaml
sed -i "s|announce_url: \"\"|announce_url: \"$ANNOUNCE_URL\"|g" config.yaml

mkdir -p auth browser_profile work

echo
echo "Telepítés kész."
echo
echo "Aktiválás:"
echo "source venv/bin/activate"
echo
