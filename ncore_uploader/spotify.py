from __future__ import annotations

import os
import base64
import re
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv
from ncore_uploader.metadata import build_spotify_music_queries


TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


@dataclass
class SpotifyAlbum:
    name: str
    artists: str
    release_date: str
    year: str
    spotify_url: str
    cover_url: str
    tracks: list[str]
    upc: str | None = None


def get_spotify_token() -> str | None:
    load_dotenv()

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        return None

    raw = f"{client_id}:{client_secret}".encode()
    auth = base64.b64encode(raw).decode()

    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=30,
    )

    if r.status_code != 200:
        print(f"Spotify token hiba: HTTP {r.status_code} {r.text[:200]}")
        return None

    return r.json().get("access_token")


def spotify_get(path: str, token: str, params: dict[str, Any] | None = None) -> dict:
    r = requests.get(
        API_BASE + path,
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )

    if r.status_code == 429:
        print("Spotify rate limit. Próbáld később.")
        return {}

    if r.status_code != 200:
        print(f"Spotify API hiba: HTTP {r.status_code} {r.text[:200]}")
        return {}

    return r.json()



def _release_album_guess_from_name(name: str) -> tuple[str, str]:
    """
    Scene zenei release névből artist/album fallback.
    Példák:
      VA-Switzerland_Top_100_Single_Charts_07.06.2026-AUDiAL_iNT
        -> VA / Switzerland Top 100 Single Charts 07 06 2026
      Junior_Reid-Junior_Reids_Classic_Hits_Vol._1-WEB-2026-PaB
        -> Junior Reid / Junior Reids Classic Hits Vol. 1
    """
    x = str(name or "").strip().split("/")[-1]
    x = x.replace("_", " ")

    # végéről scene tagek levágása
    x = re.sub(
        r"-(WEB|CD|CDS|SINGLE|EP|LP|FLAC|MP3|LOSSLESS|VINYL|AUDiAL iNT|AUDIAL INT|iNT|INT)-?(19|20)?\d{0,2}?.*$",
        "",
        x,
        flags=re.I,
    )

    # év előtti rész megtartása, de dátumos chart címnél maradjon benne a dátum
    x = re.sub(r"-(19|20)\d{2}-[A-Za-z0-9]+$", "", x)

    if x.upper().startswith("VA-"):
        album = x[3:].strip()
        album = re.sub(r"\s+", " ", album)
        return "VA", album

    if "-" in x:
        artist, album = x.split("-", 1)
        artist = re.sub(r"\s+", " ", artist).strip()
        album = re.sub(r"\s+", " ", album).strip()
        return artist, album

    return "", re.sub(r"\s+", " ", x).strip()

def search_album(artist: str, album: str, year: str | None = None) -> SpotifyAlbum | None:
    token = get_spotify_token()
    if not token:
        print("Spotify nincs konfigurálva.")
        return None

    artist = (artist or "").strip()
    album = (album or "").strip()
    year = str(year or "").strip()

    if not artist and not album:
        print("Spotify: nincs használható keresőkifejezés, kihagyom.")
        return None

    meta_for_queries = {
        "artist": artist,
        "album": album,
        "album_year": year,
        "year": year,
    }

    clean_queries = build_spotify_music_queries(meta_for_queries)

    if not clean_queries and album:
        if year:
            clean_queries.append(f'album:"{album}" year:{year}')
        clean_queries.append(f'album:"{album}"')
        clean_queries.append(album)

    clean_queries = list(dict.fromkeys(q.strip() for q in clean_queries if q and q.strip()))

    query_parts = []
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if album:
        query_parts.append(f'album:"{album}"')
    if year:
        query_parts.append(f"year:{year}")

    q = " ".join(query_parts) if query_parts else f"{artist} {album}".strip()

    search_queries = [q]

    loose_artist = artist.replace(" x ", " ").replace("&", " ")
    loose_query = " ".join(x for x in [loose_artist, album] if x).strip()
    if loose_query and loose_query not in search_queries:
        search_queries.append(loose_query)

    title_only = album.strip()
    if title_only and title_only not in search_queries:
        search_queries.append(title_only)

    items = []
    used_query = ""

    for sq in clean_queries:
        data = spotify_get(
            "/search",
            token,
            {
                "q": sq,
                "type": "album",
                "limit": 10,
                "market": "HU",
            },
        )
        found = data.get("albums", {}).get("items", [])
        if found:
            items = found
            used_query = sq
            print(f"Spotify keresés találat ezzel: {sq}")
            break
    if not items:
        print("Spotify: nincs album/single találat.")
        manual = input("Spotify album URL vagy ID [Enter = kihagy]: ").strip()
        if manual:
            return get_album_by_id_or_url(manual)
        return None

    def score_item(item):
        name = (item.get("name") or "").lower().strip()
        target = (album or "").lower().strip()
        score = 0
        if name == target:
            score += 100
        if target and target in name:
            score += 30
        if "remix" in name and name != target:
            score -= 20
        artists_text = " ".join(a.get("name", "") for a in item.get("artists", [])).lower()
        for part in artist.lower().replace(" x ", " ").split():
            if part and part in artists_text:
                score += 5
        return score

    items = sorted(items, key=score_item, reverse=True)

    def score_item(item):
        name = (item.get("name") or "").lower().strip()
        target = (album or "").lower().strip()
        score = 0

        if name == target:
            score += 100
        if target and target in name:
            score += 30
        if "remix" in name and name != target:
            score -= 20

        artists_text = " ".join(a.get("name", "") for a in item.get("artists", [])).lower()
        for part in artist.lower().replace(" x ", " ").split():
            if part and part in artists_text:
                score += 5

        return score

    items = sorted(items, key=score_item, reverse=True)

    print("\nSpotify találatok:")
    for i, item in enumerate(items, start=1):
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        print(f"{i}. {artists} - {item.get('name','')} ({item.get('release_date','')})")

    choice = input("Spotify választás [Enter = 1, 0 = kihagy]: ").strip()
    if choice == "0":
        return None
    if not choice:
        choice = "1"

    try:
        selected = items[int(choice) - 1]
    except Exception:
        return None

    album_id = selected["id"]
    details = spotify_get(f"/albums/{album_id}", token, {"market": "HU"})
    if not details:
        return None

    artists = ", ".join(a["name"] for a in details.get("artists", []))
    release_date = details.get("release_date", "")
    images = details.get("images", [])
    cover_url = images[0]["url"] if images else ""
    external_urls = details.get("external_urls", {})
    spotify_url = external_urls.get("spotify", "")

    tracks = []
    for t in details.get("tracks", {}).get("items", []):
        number = t.get("track_number")
        name = t.get("name", "")
        duration_ms = t.get("duration_ms")
        duration = ""
        if isinstance(duration_ms, int):
            sec = duration_ms // 1000
            duration = f"{sec // 60}:{sec % 60:02d}"
        tracks.append(f"{number:02d}. {name}" + (f" [{duration}]" if duration else ""))

    external_ids = details.get("external_ids", {}) or {}
    upc = external_ids.get("upc")

    return SpotifyAlbum(
        name=details.get("name", ""),
        artists=artists,
        release_date=release_date,
        year=release_date[:4] if release_date[:4].isdigit() else "",
        spotify_url=spotify_url,
        cover_url=cover_url,
        tracks=tracks,
        upc=upc,
    )


def enrich_music_with_spotify(meta: dict) -> dict:
    artist = str(meta.get("artist") or "").strip()
    album = str(meta.get("album") or "").strip()
    year = str(meta.get("album_year") or meta.get("year") or "").strip()

    # Ha a meta még üres, próbáljuk a release/mappa nevéből.
    release_name = (
        meta.get("release_name")
        or meta.get("name")
        or meta.get("torrent_name")
        or meta.get("path")
        or meta.get("source_path")
        or ""
    )

    if (not artist or not album) and release_name:
        guessed_artist, guessed_album = _release_album_guess_from_name(str(release_name))
        if not artist and guessed_artist:
            artist = guessed_artist
            meta["artist"] = guessed_artist
        if not album and guessed_album:
            album = guessed_album
            meta["album"] = guessed_album

    result = search_album(artist, album, year or None)

    if not result:
        return meta

    artists = getattr(result, "artists", None)
    if artists:
        if isinstance(artists, (list, tuple)):
            meta["artist"] = ", ".join(str(x) for x in artists if x)
        else:
            meta["artist"] = str(artists)
    if getattr(result, "name", None):
        meta["album"] = result.name
    if result.year:
        meta["album_year"] = result.year
    if result.spotify_url:
        meta["spotify_url"] = result.spotify_url
    if result.cover_url:
        meta["spotify_cover_url"] = result.cover_url

    print("Spotify metaadatok beolvasva.")
    return meta

def spotify_album_id_from_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if "open.spotify.com/album/" in value:
        return value.split("/album/", 1)[1].split("?", 1)[0].split("/", 1)[0]
    return value


def get_album_by_id_or_url(value: str) -> SpotifyAlbum | None:
    token = get_spotify_token()
    if not token:
        print("Spotify nincs konfigurálva.")
        return None

    album_id = spotify_album_id_from_url(value)
    if not album_id:
        return None

    details = spotify_get(f"/albums/{album_id}", token, {"market": "HU"})
    if not details:
        return None

    artists = ", ".join(a["name"] for a in details.get("artists", []))
    release_date = details.get("release_date", "")
    images = details.get("images", [])
    cover_url = images[0]["url"] if images else ""
    spotify_url = details.get("external_urls", {}).get("spotify", "")

    tracks = []
    for t in details.get("tracks", {}).get("items", []):
        number = t.get("track_number")
        name = t.get("name", "")
        duration_ms = t.get("duration_ms")
        duration = ""
        if isinstance(duration_ms, int):
            sec = duration_ms // 1000
            duration = f"{sec // 60}:{sec % 60:02d}"
        tracks.append(f"{number:02d}. {name}" + (f" [{duration}]" if duration else ""))

    external_ids = details.get("external_ids", {}) or {}

    return SpotifyAlbum(
        name=details.get("name", ""),
        artists=artists,
        release_date=release_date,
        year=release_date[:4] if release_date[:4].isdigit() else "",
        spotify_url=spotify_url,
        cover_url=cover_url,
        tracks=tracks,
        upc=external_ids.get("upc"),
    )


# --- broad Spotify enrichment v13 ---

def _spotify_broad_terms(meta: dict) -> list[str]:
    import re

    artist = str(meta.get("artist", "") or "").strip()
    album = str(meta.get("album", "") or "").strip()
    release_name = str(meta.get("release_name", "") or "").strip()

    terms = []

    if artist and album:
        terms.append(f"{artist} {album}")

    if album:
        terms.append(album)

    if release_name:
        x = release_name
        x = re.sub(r"\[(FLAC|MP3|AAC|WEB|CD|LOSSLESS)\]", " ", x, flags=re.I)
        x = re.sub(r"\((19\d{2}|20\d{2})\)", " ", x)
        x = re.sub(r"[-_]+", " ", x)
        x = re.sub(r"\b(FLAC|MP3|WEB|CD|SINGLE|EP|ALBUM|LOSSLESS|24BIT|16BIT)\b", " ", x, flags=re.I)
        x = re.sub(r"\s+", " ", x).strip()
        terms.append(x)

    extra = []
    for t in terms:
        extra.append(re.sub(r"\bVol\.\s*(\d+)", r"Volume \1", t, flags=re.I))
        extra.append(re.sub(r"\bVolume\s*(\d+)", r"Vol. \1", t, flags=re.I))

    terms.extend(extra)

    out = []
    for t in terms:
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) >= 4 and t not in out:
            out.append(t)

    return out[:8]


def _spotify_score(meta: dict, item: dict) -> int:
    import re

    artist = str(meta.get("artist", "") or "").lower()
    album = str(meta.get("album", "") or "").lower()

    title = item.get("name", "")
    artists = " ".join(a.get("name", "") for a in item.get("artists", []))
    hay = f"{artists} {title}".lower()

    def tokens(x: str) -> set[str]:
        return {w for w in re.split(r"[^a-z0-9]+", x.lower()) if len(w) >= 3}

    score = 0
    for tok in tokens(artist):
        if tok in hay:
            score += 3

    album_tokens = tokens(album)
    for tok in album_tokens:
        if tok in hay:
            score += 4

    if album_tokens:
        score += int(20 * len([t for t in album_tokens if t in hay]) / len(album_tokens))

    return score


def _apply_spotify_album_item(meta: dict, item: dict, token: str) -> dict:
    album_id = item.get("id")
    if not album_id:
        return meta

    detail = spotify_get(f"/albums/{album_id}", token, {"market": "HU"})

    meta["spotify_url"] = detail.get("external_urls", {}).get("spotify", "")
    if detail.get("images") and not meta.get("spotify_cover_url"):
        meta["spotify_cover_url"] = detail["images"][0].get("url", "")

    if detail.get("release_date") and not meta.get("album_year"):
        meta["album_year"] = detail["release_date"][:4]

    if detail.get("name") and not meta.get("album"):
        meta["album"] = detail["name"]

    artists = ", ".join(a.get("name", "") for a in detail.get("artists", []))
    if artists and not meta.get("artist"):
        meta["artist"] = artists

    tracks = []
    for i, tr in enumerate(detail.get("tracks", {}).get("items", []), start=1):
        name = tr.get("name", "")
        if name:
            tracks.append(f"{i:02d}. {name}")

    if tracks and not meta.get("tracklist"):
        meta["tracklist"] = "\n".join(tracks)

    upc = detail.get("external_ids", {}).get("upc")
    if upc and not meta.get("barcode"):
        meta["barcode"] = upc

    return meta


def enrich_music_with_spotify(meta: dict) -> dict:
    if meta.get("spotify_url"):
        return meta

    token = get_spotify_token()
    if not token:
        return meta

    best = None
    best_score = -1

    for q in _spotify_broad_terms(meta):
        try:
            data = spotify_get(
                "/search",
                token,
                {
                    "q": q,
                    "type": "album",
                    "limit": 10,
                    "market": "HU",
                },
            )

            for item in data.get("albums", {}).get("items", []):
                score = _spotify_score(meta, item)
                if score > best_score:
                    best_score = score
                    best = item

            if best and best_score >= 20:
                break

        except Exception as e:
            print(f"Spotify bővített keresés hiba: {e}")

    if best and best_score >= 12:
        meta = _apply_spotify_album_item(meta, best, token)
        print(f"Spotify bővített találat: {meta.get('spotify_url')} score={best_score}")
    else:
        print("Spotify bővített keresés: nincs jó találat.")

    return meta
