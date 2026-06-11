from __future__ import annotations

from pathlib import Path
import re
import requests


NCORE_MUSIC_TAGS = {
    "60s", "70s", "80s", "90s", "acid", "alternative", "ambient", "blues",
    "breaks", "classical", "country", "dance", "death.metal", "disco",
    "drum.and.bass", "dub", "dubstep", "electronic", "emo", "euro.disco",
    "euro.house", "eurodance", "europop", "experimental", "folk", "funk",
    "garage", "goa.trance", "grunge", "hardcore", "hardcore.dance",
    "hardstyle", "hip.hop", "house", "indie.rock", "industrial",
    "italo.disco", "jazz", "latin", "live", "metal", "musical",
    "new.age", "ost", "pop", "pop.rock", "progressive.house",
    "progressive.rock", "progressive.trance", "psychedelic", "psytrance",
    "punk", "reggae", "rhythm.and.blues", "rock", "ska", "soul",
    "synth.pop", "techno", "trance", "trip.hop", "uk.garage", "world.music",
}


ALIASES = {
    "hip hop": "hip.hop",
    "hip-hop": "hip.hop",
    "rnb": "rhythm.and.blues",
    "r&b": "rhythm.and.blues",
    "dnb": "drum.and.bass",
    "drum and bass": "drum.and.bass",
    "synthpop": "synth.pop",
    "synth pop": "synth.pop",
    "progressive rock": "progressive.rock",
    "progressive house": "progressive.house",
    "progressive trance": "progressive.trance",
    "world": "world.music",
    "soundtrack": "ost",
    "score": "ost",
    "edm": "electronic",
    "electronica": "electronic",
}


def normalize_style_tag(raw: str) -> str | None:
    s = raw.lower().strip()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9&. ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    if s in ALIASES:
        return ALIASES[s]

    dotted = s.replace(" ", ".")
    if dotted in NCORE_MUSIC_TAGS:
        return dotted

    if s in NCORE_MUSIC_TAGS:
        return s

    return None


def extract_styles_from_text(text: str, max_tags: int = 5) -> str:
    found = []

    lowered = text.lower()

    for tag in sorted(NCORE_MUSIC_TAGS, key=len, reverse=True):
        plain = tag.replace(".", " ")
        patterns = {tag, plain}
        for p in patterns:
            if re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", lowered):
                if tag not in found:
                    found.append(tag)
                break
        if len(found) >= max_tags:
            break

    for alias, tag in ALIASES.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered):
            if tag not in found:
                found.append(tag)
        if len(found) >= max_tags:
            break

    return ", ".join(found[:max_tags])


def parse_music_release(name: str) -> dict:
    base = Path(name).name

    pattern = re.compile(
        r"^(?P<artist>.+?)_-_(?P<title>.+?)-"
        r"(?:\((?P<catalogue>[^)]+)\)-)?"
        r"(?P<rtype>ALBUM|SINGLE|EP|WEB)-"
        r"(?P<source>WEB|CD|VINYL|TAPE)-"
        r"(?P<year>19\d{2}|20\d{2})-"
        r"(?P<group>.+)$",
        re.I,
    )

    m = pattern.match(base)
    if not m:
        return {}

    d = m.groupdict()

    artist = d["artist"].replace("_x_", " x ").replace("_", " ").strip()
    title = d["title"].replace("_", " ").strip()

    return {
        "artist": artist,
        "album": title,
        "album_year": d.get("year"),
        "barcode": d.get("catalogue") if str(d.get("catalogue", "")).isdigit() else "",
        "catalogue": d.get("catalogue"),
        "release_type": d.get("rtype"),
        "music_source": d.get("source"),
        "release_group": d.get("group"),
    }


def find_nfo_file(release_path: Path) -> Path | None:
    folder = release_path if release_path.is_dir() else release_path.parent
    nfos = list(folder.rglob("*.nfo"))
    if not nfos:
        return None

    root = [p for p in nfos if p.parent == folder]
    return root[0] if root else nfos[0]


def style_from_nfo(release_path: Path) -> str:
    nfo = find_nfo_file(release_path)
    if not nfo:
        return ""

    try:
        text = nfo.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    return extract_styles_from_text(text)


def musicbrainz_lookup_style(meta: dict) -> str:
    artist = meta.get("artist", "")
    album = meta.get("album", "")
    barcode = meta.get("barcode", "")

    query_parts = []
    if barcode:
        query_parts.append(f'barcode:"{barcode}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if album:
        query_parts.append(f'release:"{album}"')

    if not query_parts:
        return ""

    url = "https://musicbrainz.org/ws/2/release/"
    params = {
        "query": " AND ".join(query_parts),
        "fmt": "json",
        "limit": "5",
    }

    headers = {
        "User-Agent": "ncore-universal-uploader/0.2 (local script)",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"MusicBrainz keresés nem sikerült: {e}")
        return ""

    texts = []
    for rel in data.get("releases", []):
        texts.append(rel.get("title", ""))
        for tag in rel.get("tags", []):
            texts.append(tag.get("name", ""))
        for genre in rel.get("genres", []):
            texts.append(genre.get("name", ""))

    return extract_styles_from_text(" ".join(texts))


def infer_music_style(release_path: Path, meta: dict) -> str:
    style = style_from_nfo(release_path)
    if style:
        print(f"Zenei stílus NFO-ból: {style}")
        return style

    style = musicbrainz_lookup_style(meta)
    if style:
        print(f"Zenei stílus MusicBrainz-ből: {style}")
        return style

    # Fallback: release név + előadó/cím alapján.
    combined = " ".join([
        release_path.name,
        str(meta.get("artist", "")),
        str(meta.get("album", "")),
    ])

    style = extract_styles_from_text(combined)
    if style:
        print(f"Zenei stílus release névből: {style}")
        return style

    # Gyakori dance/pop előadók esetén biztonságos fallback.
    artist = str(meta.get("artist", "")).lower()
    if any(x in artist for x in ["otilia", "tom boxer", "inna", "akcent", "edward maya"]):
        print("Zenei stílus fallback: dance, pop")
        return "dance, pop"

    return ""


def find_local_cover(release_path: Path) -> Path | None:
    folder = release_path if release_path.is_dir() else release_path.parent

    names = [
        "cover", "folder", "front", "album", "artwork",
    ]
    exts = {".jpg", ".jpeg", ".png", ".webp"}

    candidates = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        score = 0
        stem = p.stem.lower()
        if stem in names:
            score += 100
        if any(n in stem for n in names):
            score += 50
        if p.parent == folder:
            score += 20
        candidates.append((score, p))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0][1]


def musicbrainz_cover_url(meta: dict) -> str | None:
    artist = meta.get("artist", "")
    album = meta.get("album", "")
    barcode = meta.get("barcode", "")

    query_parts = []
    if barcode:
        query_parts.append(f'barcode:"{barcode}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if album:
        query_parts.append(f'release:"{album}"')

    if not query_parts:
        return None

    url = "https://musicbrainz.org/ws/2/release/"
    params = {
        "query": " AND ".join(query_parts),
        "fmt": "json",
        "limit": "5",
    }
    headers = {
        "User-Agent": "ncore-universal-uploader/0.2 (local script)",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        releases = r.json().get("releases", [])
    except Exception as e:
        print(f"MusicBrainz cover keresés nem sikerült: {e}")
        return None

    for rel in releases:
        mbid = rel.get("id")
        if not mbid:
            continue
        cover_url = f"https://coverartarchive.org/release/{mbid}/front"
        try:
            cr = requests.get(cover_url, allow_redirects=True, timeout=20)
            if cr.status_code == 200 and cr.headers.get("content-type", "").startswith("image/"):
                return cover_url
        except Exception:
            continue

    return None


def build_music_techinfo(release_path: Path, meta: dict, output_dir: Path) -> Path:
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{release_path.name}.music.techinfo.txt"

    folder = release_path if release_path.is_dir() else release_path.parent
    audio_exts = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg"}
    files = sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in audio_exts])

    lines = []
    lines.append("Music technical information")
    lines.append("")
    lines.append(f"Release: {release_path.name}")
    if meta.get("artist"):
        lines.append(f"Artist: {meta['artist']}")
    if meta.get("album"):
        lines.append(f"Album: {meta['album']}")
    if meta.get("album_year"):
        lines.append(f"Year: {meta['album_year']}")
    if meta.get("music_style"):
        lines.append(f"Style: {meta['music_style']}")
    lines.append("")
    lines.append("Files:")

    for idx, f in enumerate(files, start=1):
        lines.append("")
        lines.append(f"{idx:02d}. {f.name}")
        try:
            r = subprocess.run(
                ["mediainfo", str(f)],
                capture_output=True,
                text=True,
                check=False,
            )
            txt = r.stdout

            wanted = []
            for line in txt.splitlines():
                low = line.lower()
                if any(k in low for k in [
                    "format ",
                    "format/profile",
                    "bit rate",
                    "channel",
                    "sampling rate",
                    "bit depth",
                    "duration",
                    "writing library",
                ]):
                    wanted.append(line)

            for line in wanted[:20]:
                lines.append("    " + line)
        except Exception as e:
            lines.append(f"    MediaInfo error: {e}")

    if not files:
        lines.append("No audio files found.")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_music_generated_nfo(release_path: Path, meta: dict, output_dir: Path) -> Path:
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{release_path.name}.generated.nfo"

    folder = release_path if release_path.is_dir() else release_path.parent
    audio_exts = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg"}
    files = sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in audio_exts])

    lines = []
    lines.append(release_path.name)
    lines.append("=" * len(release_path.name))
    lines.append("")
    lines.append("Release information")
    lines.append("-------------------")
    lines.append(f"Artist.......: {meta.get('artist', '')}")
    lines.append(f"Album........: {meta.get('album', '')}")
    lines.append(f"Year.........: {meta.get('album_year', '')}")
    lines.append(f"Style........: {meta.get('music_style', '')}")
    if meta.get("barcode"):
        lines.append(f"Barcode......: {meta.get('barcode')}")
    if meta.get("release_type"):
        lines.append(f"Type.........: {meta.get('release_type')}")
    if meta.get("music_source"):
        lines.append(f"Source.......: {meta.get('music_source')}")
    if meta.get("release_group"):
        lines.append(f"Group........: {meta.get('release_group')}")
    if meta.get("spotify_url"):
        lines.append(f"Spotify......: {meta.get('spotify_url')}")
    if meta.get("discogs_url"):
        lines.append(f"Discogs......: {meta.get('discogs_url')}")
    if meta.get("musicbrainz_url"):
        lines.append(f"MusicBrainz..: {meta.get('musicbrainz_url')}")
    lines.append("")

    lines.append("Tracklist")
    lines.append("---------")

    if meta.get("tracklist"):
        lines.extend(str(meta["tracklist"]).splitlines())
    elif files:
        for idx, f in enumerate(files, start=1):
            duration = ""
            try:
                r = subprocess.run(
                    [
                        "mediainfo",
                        "--Inform=Audio;%Duration/String3%",
                        str(f),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                duration = r.stdout.strip()
            except Exception:
                duration = ""

            title = f.stem
            title = title.replace("_", " ")
            lines.append(f"{idx:02d}. {title}" + (f" [{duration}]" if duration else ""))
    else:
        lines.append("No audio files found.")

    lines.append("")
    lines.append("Technical information")
    lines.append("---------------------")

    for idx, f in enumerate(files, start=1):
        lines.append("")
        lines.append(f"{idx:02d}. {f.name}")

        try:
            r = subprocess.run(
                ["mediainfo", str(f)],
                capture_output=True,
                text=True,
                check=False,
            )
            txt = r.stdout

            wanted = []
            for line in txt.splitlines():
                low = line.lower()
                if any(k in low for k in [
                    "format ",
                    "format/profile",
                    "duration",
                    "bit rate mode",
                    "bit rate",
                    "channel",
                    "sampling rate",
                    "bit depth",
                    "writing library",
                ]):
                    if line not in wanted:
                        wanted.append(line)

            for line in wanted[:24]:
                lines.append("    " + line)
        except Exception as e:
            lines.append(f"    MediaInfo error: {e}")

    lines.append("")
    lines.append("Generated by nCore universal uploader.")
    lines.append("This is a generated NFO because no original NFO was found.")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def read_audio_tag(file_path: Path, tag: str) -> str:
    import subprocess

    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", f"format_tags={tag}",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def build_tracklist_from_tags(release_path: Path) -> str:
    folder = release_path if release_path.is_dir() else release_path.parent
    audio_exts = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg"}

    files = sorted([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in audio_exts])
    lines = []

    for idx, f in enumerate(files, start=1):
        track = read_audio_tag(f, "track")
        title = read_audio_tag(f, "title")

        if not title:
            title = f.stem.replace("_", " ")

        if track:
            track = track.split("/")[0].zfill(2)
        else:
            track = str(idx).zfill(2)

        lines.append(f"{track}. {title}")

    return "\n".join(lines)


def musicbrainz_enrich_metadata(meta: dict) -> dict:
    artist = meta.get("artist", "")
    album = meta.get("album", "")
    barcode = meta.get("barcode", "")

    query_parts = []
    if barcode:
        query_parts.append(f'barcode:"{barcode}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if album:
        query_parts.append(f'release:"{album}"')

    if not query_parts:
        return meta

    url = "https://musicbrainz.org/ws/2/release/"
    params = {
        "query": " AND ".join(query_parts),
        "fmt": "json",
        "limit": "5",
        "inc": "artist-credits+release-groups+tags+genres",
    }
    headers = {
        "User-Agent": "ncore-universal-uploader/0.2 (local script)",
    }

    try:
        r = requests.get(url, params=params, headers=headers, timeout=25)
        r.raise_for_status()
        releases = r.json().get("releases", [])
    except Exception as e:
        print(f"MusicBrainz metaadat keresés nem sikerült: {e}")
        return meta

    if not releases:
        return meta

    print("\nMusicBrainz találatok:")
    for i, rel in enumerate(releases[:5], start=1):
        title = rel.get("title", "")
        date = rel.get("date", "")
        country = rel.get("country", "")
        print(f"{i}. {title} ({date[:4]}) [{country}]")

    choice = input("MusicBrainz választás [Enter = 1, 0 = kihagy]: ").strip()
    if choice == "0":
        return meta
    if not choice:
        choice = "1"

    try:
        rel = releases[int(choice) - 1]
    except Exception:
        return meta

    mbid = rel.get("id")
    if mbid:
        meta["musicbrainz_url"] = f"https://musicbrainz.org/release/{mbid}"
        meta["musicbrainz_id"] = mbid

        if not meta.get("musicbrainz_cover_url"):
            cover_url = f"https://coverartarchive.org/release/{mbid}/front"
            try:
                cr = requests.get(cover_url, allow_redirects=True, timeout=15)
                if cr.status_code == 200 and cr.headers.get("content-type", "").startswith("image/"):
                    meta["musicbrainz_cover_url"] = cover_url
            except Exception:
                pass

    if rel.get("date") and not meta.get("album_year"):
        date = rel["date"]
        if date[:4].isdigit():
            meta["album_year"] = date[:4]

    if not meta.get("album"):
        meta["album"] = rel.get("title", "")

    texts = []
    for tag in rel.get("tags", []):
        texts.append(tag.get("name", ""))
    for genre in rel.get("genres", []):
        texts.append(genre.get("name", ""))

    style = extract_styles_from_text(" ".join(texts))
    if style and not meta.get("music_style"):
        meta["music_style"] = style
        print(f"Zenei stílus MusicBrainz-ből: {style}")

    return meta


def cover_url_from_nfo(release_path: Path) -> str:
    nfo = find_nfo_file(release_path)
    if not nfo:
        return ""

    try:
        text = nfo.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    m = re.search(r"https?://\\S+\\.(?:jpg|jpeg|png|webp)(?:\\?\\S*)?", text, re.I)
    if m:
        return m.group(0).strip()

    return ""


def enrich_music_metadata(meta: dict, discogs_token: str | None = None) -> dict:
    discogs = discogs_search_release(meta, discogs_token)
    if discogs:
        meta.update({k: v for k, v in discogs.items() if v})
        if meta.get("music_style"):
            print(f"Zenei stílus Discogs-ból: {meta['music_style']}")

    return meta

# --- override parse_music_release v2 ---

def parse_music_release(name: str) -> dict:
    base = Path(name).name

    patterns = [
        # Artist_-_Album-(CATALOG)-SINGLE-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)_-_(?P<title>.+?)-"
            r"(?:\((?P<catalogue>[^)]+)\)-)?"
            r"(?P<rtype>ALBUM|SINGLE|EP)-(?P<source>WEB|CD|VINYL|TAPE)-"
            r"(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),
        # Artist-Album-CD-2026-GRP vagy Artist-Album-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)-"
            r"(?P<source>WEB|CD|VINYL|TAPE)-"
            r"(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),
    ]

    m = None
    for pat in patterns:
        m = pat.match(base)
        if m:
            break

    if not m:
        return {}

    d = m.groupdict()
    artist = d.get("artist", "").replace("_x_", " x ").replace("_and_", " and ").replace("_", " ").strip()
    title = d.get("title", "").replace("_", " ").strip()
    source = d.get("source", "")
    rtype = d.get("rtype") or ("ALBUM" if source.upper() in {"CD", "VINYL", "TAPE"} else "SINGLE")
    catalogue = d.get("catalogue") or ""

    return {
        "artist": artist,
        "album": title,
        "album_year": d.get("year"),
        "barcode": catalogue if str(catalogue).isdigit() else "",
        "catalogue": catalogue,
        "release_type": rtype,
        "music_source": source,
        "release_group": d.get("group"),
    }


def discogs_search_release(meta: dict, token: str | None = None) -> dict:
    try:
        from ncore_uploader.discogs import search_release
    except Exception as e:
        print(f"Discogs modul nem elérhető: {e}")
        return {}

    if not token:
        return {}

    artist = meta.get("artist", "")
    album = meta.get("album", "")
    barcode = meta.get("barcode", "")

    try:
        results = search_release(artist, album, barcode)
        if not results and barcode:
            print("Nincs Discogs találat katalógus/barcode alapján, próbálom előadó + cím alapján...")
            results = search_release(artist, album, "")
    except Exception as e:
        print(f"Discogs keresés nem sikerült: {e}")
        return {}

    if not results:
        print("Nincs Discogs találat.")
        return {}

    print("\nDiscogs találatok:")
    for i, r in enumerate(results[:5], start=1):
        print(f"{i}. {r.title} ({r.year}) [{r.country}]")

    choice = input("Discogs választás [Enter = 1, 0 = kihagy]: ").strip()
    if choice == "0":
        return {}
    if not choice:
        choice = "1"

    try:
        selected = results[int(choice) - 1]
    except Exception:
        return {}

    out = {
        "discogs_url": f"https://www.discogs.com{selected.uri}" if selected.uri else "",
        "discogs_cover_url": selected.cover_image or "",
    }

    text = " ".join((selected.genre or []) + (selected.style or []))
    style = extract_styles_from_text(text)
    if style:
        out["music_style"] = style

    if selected.year and not meta.get("album_year"):
        out["album_year"] = selected.year

    return out


# --- VA parser override v3 ---
def parse_music_release(name: str) -> dict:
    base = Path(name).name

    patterns = [
        # VA-Switzerland_Top_100_Single_Charts_07.06.2026-AUDiAL_iNT
        re.compile(
            r"^(?P<artist>VA|Various_Artists|Various.Artists)-(?P<title>.+?)-(?P<group>[A-Za-z0-9_]+)$",
            re.I,
        ),

        # Artist_-_Album-(CATALOG)-SINGLE-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)_-_(?P<title>.+?)-"
            r"(?:\((?P<catalogue>[^)]+)\)-)?"
            r"(?P<rtype>ALBUM|SINGLE|EP)-(?P<source>WEB|CD|VINYL|TAPE)-"
            r"(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # Artist-Album-CD-2026-GRP vagy Artist-Album-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)-"
            r"(?P<source>WEB|CD|VINYL|TAPE)-"
            r"(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),
    ]

    m = None
    for pat in patterns:
        m = pat.match(base)
        if m:
            break

    if not m:
        return {}

    d = m.groupdict()

    raw_artist = d.get("artist", "")
    raw_title = d.get("title", "")

    is_va = raw_artist.lower() in {"va", "various_artists", "various.artists"}

    artist = "Various Artists" if is_va else (
        raw_artist
        .replace("_x_", " x ")
        .replace("_and_", " and ")
        .replace("_", " ")
        .strip()
    )

    title = raw_title.replace("_", " ").replace(".", ".").strip()

    # VA chart release-ekben gyakran a dátum a cím része.
    year = d.get("year") or ""
    if not year:
        ym = re.search(r"(19\d{2}|20\d{2})", title)
        if ym:
            year = ym.group(1)

    source = d.get("source") or "WEB"
    rtype = d.get("rtype") or ("ALBUM" if source.upper() in {"CD", "VINYL", "TAPE"} else "SINGLE")
    catalogue = d.get("catalogue") or ""

    return {
        "artist": artist,
        "album": title,
        "album_year": year,
        "barcode": catalogue if str(catalogue).isdigit() else "",
        "catalogue": catalogue,
        "release_type": rtype,
        "music_source": source,
        "release_group": d.get("group"),
        "is_va": is_va,
    }


# --- FLAC scene parser override v4 ---
_old_parse_music_release_v4 = parse_music_release

def parse_music_release(name: str) -> dict:
    base = Path(name).name

    # Artist-Album-(CATALOG)-CD-FLAC-2023-GRP
    m = re.match(
        r"^(?P<artist>.+?)-(?P<title>.+?)-"
        r"(?:\((?P<catalogue>[^)]+)\)-)?"
        r"(?P<source>CD|WEB|VINYL|TAPE)-"
        r"(?P<format>FLAC|MP3|AAC|M4A)-"
        r"(?P<year>19\d{2}|20\d{2})-"
        r"(?P<group>.+)$",
        base,
        re.I,
    )

    if m:
        d = m.groupdict()
        artist = (
            d.get("artist", "")
            .replace("_x_", " x ")
            .replace("_and_", " and ")
            .replace("_", " ")
            .strip()
        )
        title = d.get("title", "").replace("_", " ").strip()
        catalogue = d.get("catalogue") or ""

        return {
            "artist": artist,
            "album": title,
            "album_year": d.get("year"),
            "barcode": catalogue if str(catalogue).isdigit() else "",
            "catalogue": catalogue,
            "release_type": "ALBUM",
            "music_source": d.get("source"),
            "music_format": d.get("format"),
            "release_group": d.get("group"),
            "is_va": artist.lower() in {"va", "various artists"},
        }

    return _old_parse_music_release_v4(name)


# --- scene music parser override v5 ---
_old_parse_music_release_v5 = parse_music_release

def _clean_scene_text_v5(value: str) -> str:
    return (
        (value or "")
        .replace("_x_", " x ")
        .replace("_and_", " and ")
        .replace("_And_", " And ")
        .replace("_-_", " - ")
        .replace("_", " ")
        .strip(" -")
    )


def parse_music_release(name: str) -> dict:
    base = Path(name).name

    patterns = [
        # VA_-_Album-(CAT)-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>VA|Various_Artists|Various\.Artists)_-_(?P<title>.+?)"
            r"(?:-\((?P<catalogue>[^)]+)\))?"
            r"-(?P<source>WEB|CD|VINYL|TAPE)"
            r"(?:-(?P<format>FLAC|MP3|AAC|M4A))?"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # VA-Album-(CAT)-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>VA|Various_Artists|Various\.Artists)-(?P<title>.+?)"
            r"(?:-\((?P<catalogue>[^)]+)\))?"
            r"-(?P<source>WEB|CD|VINYL|TAPE)"
            r"(?:-(?P<format>FLAC|MP3|AAC|M4A))?"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # Artist-Album-(CAT)-SINGLE-24BIT-WEB-FLAC-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)"
            r"(?:-\((?P<catalogue>[^)]+)\))?"
            r"-(?P<rtype>SINGLE|EP|ALBUM)"
            r"(?:-(?P<bitdepth>16BIT|24BIT))?"
            r"-(?P<source>WEB|CD|VINYL|TAPE)"
            r"(?:-(?P<format>FLAC|MP3|AAC|M4A))?"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # Artist-Album-(CAT)-24BIT-WEB-FLAC-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)"
            r"(?:-\((?P<catalogue>[^)]+)\))?"
            r"(?:-(?P<bitdepth>16BIT|24BIT))"
            r"-(?P<source>WEB|CD|VINYL|TAPE)"
            r"(?:-(?P<format>FLAC|MP3|AAC|M4A))?"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # Artist-Album-CAT-16BIT-WEB-FLAC-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)-(?P<catalogue>[A-Z0-9_.]+)"
            r"-(?P<bitdepth>16BIT|24BIT)"
            r"-(?P<source>WEB|CD|VINYL|TAPE)"
            r"(?:-(?P<format>FLAC|MP3|AAC|M4A))?"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # Artist-Album-(CAT)-CD-FLAC-2023-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)"
            r"(?:-\((?P<catalogue>[^)]+)\))?"
            r"-(?P<source>CD|WEB|VINYL|TAPE)"
            r"-(?P<format>FLAC|MP3|AAC|M4A)"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),

        # Artist-Album-WEB-2026-GRP
        re.compile(
            r"^(?P<artist>.+?)-(?P<title>.+?)"
            r"-(?P<source>WEB|CD|VINYL|TAPE)"
            r"-(?P<year>19\d{2}|20\d{2})-(?P<group>.+)$",
            re.I,
        ),
    ]

    m = None
    for pat in patterns:
        m = pat.match(base)
        if m:
            break

    if not m:
        return _old_parse_music_release_v5(name)

    d = m.groupdict()
    raw_artist = d.get("artist", "")
    is_va = raw_artist.lower() in {"va", "various_artists", "various.artists"}

    artist = "Various Artists" if is_va else _clean_scene_text_v5(raw_artist)
    title = _clean_scene_text_v5(d.get("title", ""))
    catalogue = d.get("catalogue") or ""
    source = d.get("source") or ""
    fmt = d.get("format") or ""
    rtype = d.get("rtype") or ("ALBUM" if source.upper() in {"CD", "VINYL", "TAPE"} else "ALBUM")

    return {
        "artist": artist,
        "album": title,
        "album_year": d.get("year"),
        "barcode": catalogue if str(catalogue).isdigit() else "",
        "catalogue": catalogue,
        "release_type": rtype,
        "music_source": source,
        "music_format": fmt,
        "bitdepth": d.get("bitdepth") or "",
        "release_group": d.get("group"),
        "is_va": is_va,
    }


# --- scene music parser override v6 ---
_old_parse_music_release_v6 = parse_music_release

def parse_music_release(name: str) -> dict:
    meta = _old_parse_music_release_v6(name)

    # Artist-Title-CAT-16BIT-WEB-FLAC-YYYY-GRP eset:
    # pl. Paul_Deep-Tique-SB291-16BIT-WEB-FLAC-2026-WAVED
    if meta and not meta.get("catalogue") and meta.get("album"):
        m = re.match(r"^(?P<title>.+)-(?P<cat>[A-Z]{1,10}\d{1,10}[A-Z0-9]*)$", meta["album"], re.I)
        if m:
            meta["album"] = m.group("title").strip()
            meta["catalogue"] = m.group("cat").strip()

    return meta


# --- scene music parser cleanup v7 ---
_old_parse_music_release_v7 = parse_music_release

def parse_music_release(name: str) -> dict:
    meta = _old_parse_music_release_v7(name)

    album = meta.get("album", "") if meta else ""
    if album:
        flags = []
        for suffix in ["-PROPER", "-REPACK", "-READNFO", "-OST"]:
            if album.upper().endswith(suffix):
                album = album[: -len(suffix)].strip(" -")
                flags.append(suffix.strip("-"))

        if flags:
            meta["album"] = album
            if "OST" in flags:
                meta["release_type"] = "OST"
            if "PROPER" in flags:
                meta["proper"] = True
            if "REPACK" in flags:
                meta["repack"] = True
            if "READNFO" in flags:
                meta["readnfo"] = True

    return meta


# --- music style fallback v8 ---
_old_infer_music_style_v8 = infer_music_style

def infer_music_style(release_path: Path, meta: dict) -> str:
    style = _old_infer_music_style_v8(release_path, meta)
    if style:
        return style

    text_parts = [
        str(meta.get("artist", "")),
        str(meta.get("album", "")),
        str(meta.get("release_name", "")),
        str(release_path.name),
    ]

    for nfo in release_path.rglob("*.nfo") if release_path.is_dir() else []:
        try:
            text_parts.append(nfo.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass

    text = " ".join(text_parts).lower()

    mapping = [
        ("drum and bass", "drum.and.bass"),
        ("drum & bass", "drum.and.bass"),
        ("dnb", "drum.and.bass"),
        ("deep house", "house"),
        ("afro house", "house"),
        ("tech house", "house"),
        ("progressive house", "progressive.house"),
        ("house", "house"),
        ("trance", "trance"),
        ("techno", "techno"),
        ("dance", "dance"),
        ("edm", "dance"),
        ("electronic", "electronic"),
        ("electronica", "electronic"),
        ("ambient", "ambient"),
        ("dubstep", "dubstep"),
        ("breaks", "breaks"),
        ("hip hop", "hip.hop"),
        ("hip-hop", "hip.hop"),
        ("rap", "hip.hop"),
        ("jazz", "jazz"),
        ("blues", "blues"),
        ("rock", "rock"),
        ("metal", "metal"),
        ("pop", "pop"),
        ("ost", "ost"),
        ("soundtrack", "ost"),
        ("classical", "classical"),
        ("reggae", "reggae"),
        ("soul", "soul"),
        ("funk", "funk"),
        ("folk", "folk"),
        ("country", "country"),
        ("latin", "latin"),
    ]

    hits = []
    for needle, tag in mapping:
        if needle in text and tag not in hits:
            hits.append(tag)

    if hits:
        style = ", ".join(hits[:5])
        print(f"Zenei stílus fallback szövegből: {style}")
        return style

    print("Zenei stílus fallback: electronic")
    return "electronic"


# --- nfo genre/style normalization v9 ---
_old_extract_styles_from_text_v9 = extract_styles_from_text

def extract_styles_from_text(text: str) -> str:
    raw = (text or "").lower()

    normalized_hits = []

    mapping = [
        ("goa", "goa.trance"),
        ("goa trance", "goa.trance"),
        ("psy trance", "psytrance"),
        ("psy-trance", "psytrance"),
        ("psytrance", "psytrance"),
        ("drum and bass", "drum.and.bass"),
        ("drum & bass", "drum.and.bass"),
        ("dnb", "drum.and.bass"),
        ("r&b", "rhythm.and.blues"),
        ("rnb", "rhythm.and.blues"),
        ("synthpop", "synth.pop"),
        ("synth pop", "synth.pop"),
        ("soundtrack", "ost"),
        ("score", "ost"),
        ("ost", "ost"),
    ]

    for needle, tag in mapping:
        if needle in raw and tag not in normalized_hits:
            normalized_hits.append(tag)

    old = _old_extract_styles_from_text_v9(text)
    if old:
        for tag in [x.strip() for x in old.split(",") if x.strip()]:
            if tag not in normalized_hits:
                normalized_hits.append(tag)

    return ", ".join(normalized_hits[:5])


# --- audio tag metadata enrichment v10 ---
def first_audio_files(release_path: Path, limit: int = 20) -> list[Path]:
    exts = {".flac", ".mp3", ".m4a", ".aac", ".wav"}
    files = [release_path] if release_path.is_file() else [p for p in release_path.rglob("*") if p.is_file()]
    audio = [p for p in files if p.suffix.lower() in exts]
    return sorted(audio, key=lambda p: str(p).lower())[:limit]


def _ffprobe_tags(path: Path) -> dict:
    import json
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(out)
        return data.get("format", {}).get("tags", {}) or {}
    except Exception:
        return {}


def _tag_get(tags: dict, *names: str) -> str:
    lowered = {str(k).lower(): str(v).strip() for k, v in tags.items() if str(v).strip()}
    for n in names:
        v = lowered.get(n.lower())
        if v:
            return v
    return ""


def clean_album_folder_guess(name: str) -> tuple[str, str]:
    import re

    x = str(name or "").strip()

    year = ""
    m = re.search(r"\((19\d{2}|20\d{2})\)", x)
    if m:
        year = m.group(1)

    x = re.sub(r"\s*\[(FLAC|MP3|AAC|M4A|WEB|CD|LOSSLESS)\]\s*$", "", x, flags=re.I)
    x = re.sub(r"\s*\((19\d{2}|20\d{2})\)\s*$", "", x)
    x = re.sub(r"\s+", " ", x).strip(" -")

    if " - " in x:
        artist, album = x.split(" - ", 1)
        return album.strip(), year

    return x, year


def enrich_music_from_audio_tags(meta: dict, release_path: Path) -> dict:
    files = first_audio_files(release_path, limit=30)
    if not files:
        return meta

    all_tags = [_ffprobe_tags(p) for p in files]
    all_tags = [t for t in all_tags if t]
    if not all_tags:
        album_guess, year_guess = clean_album_folder_guess(release_path.name)
        if album_guess and not meta.get("album"):
            meta["album"] = album_guess
        if year_guess and not meta.get("album_year"):
            meta["album_year"] = year_guess
        return meta

    first = all_tags[0]

    artist = (
        _tag_get(first, "album_artist", "albumartist", "artist")
        or _tag_get(first, "ARTIST")
    )
    album = _tag_get(first, "album", "ALBUM")
    date = _tag_get(first, "date", "year", "originaldate", "releasedate")
    genre = _tag_get(first, "genre", "style")

    if artist and not meta.get("artist"):
        meta["artist"] = artist

    if album and not meta.get("album"):
        meta["album"] = album

    if date and not meta.get("album_year"):
        import re
        m = re.search(r"(19\d{2}|20\d{2})", date)
        if m:
            meta["album_year"] = m.group(1)

    if genre and not meta.get("music_style"):
        style = extract_styles_from_text(genre)
        if style:
            meta["music_style"] = style
            print(f"Zenei stílus tagekből: {style}")

    # Folder name fallback: pl. "... (2026) [FLAC]"
    album_guess, year_guess = clean_album_folder_guess(release_path.name)
    if album_guess and (not meta.get("album") or "[FLAC]" in str(meta.get("album"))):
        meta["album"] = album_guess
    if year_guess and not meta.get("album_year"):
        meta["album_year"] = year_guess

    return meta


# --- external music db logging wrapper v11 ---
_old_enrich_music_metadata_v11 = enrich_music_metadata
_old_musicbrainz_enrich_metadata_v11 = musicbrainz_enrich_metadata

def enrich_music_metadata(meta: dict, discogs_token: str | None = None) -> dict:
    print("Discogs keresés...")
    before = dict(meta)
    meta = _old_enrich_music_metadata_v11(meta, discogs_token)

    if meta.get("discogs_url") and meta.get("discogs_url") != before.get("discogs_url"):
        print(f"Discogs találat: {meta['discogs_url']}")
    elif meta.get("discogs_url"):
        print(f"Discogs link: {meta['discogs_url']}")
    else:
        print("Discogs: nincs találat.")

    return meta


def musicbrainz_enrich_metadata(meta: dict) -> dict:
    print("MusicBrainz keresés...")
    before = dict(meta)
    meta = _old_musicbrainz_enrich_metadata_v11(meta)

    if meta.get("musicbrainz_url") and meta.get("musicbrainz_url") != before.get("musicbrainz_url"):
        print(f"MusicBrainz találat: {meta['musicbrainz_url']}")
    elif meta.get("musicbrainz_url"):
        print(f"MusicBrainz link: {meta['musicbrainz_url']}")
    else:
        print("MusicBrainz: nincs találat.")

    return meta


# --- manual Discogs URL support v12 ---
def apply_manual_music_url(meta: dict, url: str) -> dict:
    url = (url or "").strip()

    if not url:
        return meta

    if "discogs.com/release/" in url:
        meta["discogs_url"] = url.split("?")[0]
        print(f"Discogs URL kézzel megadva: {meta['discogs_url']}")
        return meta

    if "musicbrainz.org/release/" in url:
        meta["musicbrainz_url"] = url.split("?")[0]
        print(f"MusicBrainz URL kézzel megadva: {meta['musicbrainz_url']}")
        return meta

    if "open.spotify.com/album/" in url:
        meta["spotify_url"] = url.split("?")[0]
        print(f"Spotify URL kézzel megadva: {meta['spotify_url']}")
        return meta

    print("Ismeretlen zenei adatbázis URL, kihagyva.")
    return meta


# --- broad external DB search v13 ---
def _music_search_terms(meta: dict) -> list[str]:
    import re

    artist = str(meta.get("artist", "") or "").strip()
    album = str(meta.get("album", "") or "").strip()
    release_name = str(meta.get("release_name", "") or "").strip()

    texts = []

    if artist and album:
        texts.append(f"{artist} {album}")

    if album:
        texts.append(album)

    if release_name:
        x = release_name
        x = re.sub(r"\[(FLAC|MP3|AAC|WEB|CD|LOSSLESS)\]", " ", x, flags=re.I)
        x = re.sub(r"\((19\d{2}|20\d{2})\)", " ", x)
        x = re.sub(r"[-_]+", " ", x)
        x = re.sub(r"\b(FLAC|MP3|WEB|CD|SINGLE|EP|ALBUM|LOSSLESS|24BIT|16BIT)\b", " ", x, flags=re.I)
        x = re.sub(r"\s+", " ", x).strip()
        texts.append(x)

    # Dave's Picks Vol. 58 / Volume 58 variációk
    extra = []
    for t in texts:
        t2 = re.sub(r"\bVol\.\s*(\d+)", r"Volume \1", t, flags=re.I)
        t3 = re.sub(r"\bVolume\s*(\d+)", r"Vol. \1", t, flags=re.I)
        extra.extend([t2, t3])

    texts.extend(extra)

    out = []
    for t in texts:
        t = re.sub(r"\s+", " ", t).strip(" -")
        if len(t) >= 4 and t not in out:
            out.append(t)

    return out[:8]


def _score_external_result(meta: dict, text: str) -> int:
    import re

    artist = str(meta.get("artist", "") or "").lower()
    album = str(meta.get("album", "") or "").lower()
    text_l = str(text or "").lower()

    def tokens(x: str) -> set[str]:
        return {w for w in re.split(r"[^a-z0-9]+", x.lower()) if len(w) >= 3}

    score = 0

    for tok in tokens(artist):
        if tok in text_l:
            score += 3

    album_tokens = tokens(album)
    for tok in album_tokens:
        if tok in text_l:
            score += 4

    if album_tokens:
        hit_ratio = len([t for t in album_tokens if t in text_l]) / max(1, len(album_tokens))
        score += int(hit_ratio * 20)

    return score


def _normalize_external_styles(values: list[str]) -> str:
    text = " ".join(v for v in values if v)
    return extract_styles_from_text(text)


# Discogs override: több query, lazább matching, automatikus URL
_old_enrich_music_metadata_v13 = enrich_music_metadata

def enrich_music_metadata(meta: dict, discogs_token: str | None = None) -> dict:
    import requests

    if meta.get("discogs_url"):
        return meta

    token = discogs_token or ""
    if not token:
        print("Discogs: nincs token, kihagyom.")
        return meta

    print("Discogs keresés...")

    headers = {
        "User-Agent": "ncore-universal-uploader/1.0",
        "Authorization": f"Discogs token={token}",
    }

    best = None
    best_score = -1

    for q in _music_search_terms(meta):
        try:
            r = requests.get(
                "https://api.discogs.com/database/search",
                headers=headers,
                params={
                    "q": q,
                    "type": "release",
                    "per_page": 10,
                    "page": 1,
                },
                timeout=20,
            )

            if r.status_code != 200:
                print(f"Discogs API hiba: HTTP {r.status_code}")
                continue

            data = r.json()
            for item in data.get("results", []):
                title = item.get("title", "")
                year = str(item.get("year", "") or "")
                labels = " ".join(item.get("label", []) or [])
                styles = " ".join((item.get("genre", []) or []) + (item.get("style", []) or []))
                hay = " ".join([title, year, labels, styles])
                score = _score_external_result(meta, hay)

                if score > best_score:
                    best_score = score
                    best = item

            if best and best_score >= 20:
                break

        except Exception as e:
            print(f"Discogs keresés hiba: {e}")

    if not best:
        print("Discogs: nincs találat.")
        return meta

    rid = best.get("id")
    if rid:
        meta["discogs_url"] = f"https://www.discogs.com/release/{rid}"

    if best.get("cover_image") and not meta.get("discogs_cover_url"):
        meta["discogs_cover_url"] = best.get("cover_image")

    style = _normalize_external_styles((best.get("genre", []) or []) + (best.get("style", []) or []))
    if style and (not meta.get("music_style") or meta.get("music_style") == "electronic"):
        meta["music_style"] = style
        print(f"Zenei stílus Discogs-ból: {style}")

    if best.get("year") and not meta.get("album_year"):
        meta["album_year"] = str(best.get("year"))

    print(f"Discogs találat: {meta.get('discogs_url')} score={best_score}")
    return meta


# MusicBrainz override: több query, lazább matching, automatikus URL
_old_musicbrainz_enrich_metadata_v13 = musicbrainz_enrich_metadata

def musicbrainz_enrich_metadata(meta: dict) -> dict:
    import requests
    import time

    if meta.get("musicbrainz_url"):
        return meta

    print("MusicBrainz keresés...")

    headers = {
        "User-Agent": "ncore-universal-uploader/1.0 (local script)"
    }

    best = None
    best_score = -1

    for q in _music_search_terms(meta):
        queries = [
            q,
            f'release:"{q}"',
        ]

        artist = str(meta.get("artist", "") or "").strip()
        album = str(meta.get("album", "") or "").strip()
        if artist and album:
            queries.insert(0, f'artist:"{artist}" AND release:"{album}"')

        for query in queries:
            try:
                r = requests.get(
                    "https://musicbrainz.org/ws/2/release/",
                    headers=headers,
                    params={
                        "query": query,
                        "fmt": "json",
                        "limit": "10",
                    },
                    timeout=20,
                )

                if r.status_code != 200:
                    print(f"MusicBrainz API hiba: HTTP {r.status_code}")
                    continue

                data = r.json()
                for rel in data.get("releases", []):
                    title = rel.get("title", "")
                    artist_credit = " ".join(
                        ac.get("artist", {}).get("name", "")
                        for ac in rel.get("artist-credit", [])
                        if isinstance(ac, dict)
                    )
                    date = rel.get("date", "")
                    hay = " ".join([title, artist_credit, date])
                    score = _score_external_result(meta, hay)

                    if score > best_score:
                        best_score = score
                        best = rel

                if best and best_score >= 20:
                    break

            except Exception as e:
                print(f"MusicBrainz keresés hiba: {e}")

            time.sleep(1)

        if best and best_score >= 20:
            break

    if not best:
        print("MusicBrainz: nincs találat.")
        return meta

    mbid = best.get("id")
    if mbid:
        meta["musicbrainz_id"] = mbid
        meta["musicbrainz_url"] = f"https://musicbrainz.org/release/{mbid}"

    if best.get("date") and not meta.get("album_year"):
        date = best["date"]
        if len(date) >= 4 and date[:4].isdigit():
            meta["album_year"] = date[:4]

    if best.get("title") and not meta.get("album"):
        meta["album"] = best["title"]

    print(f"MusicBrainz találat: {meta.get('musicbrainz_url')} score={best_score}")
    return meta


# --- artist based style fallback v14 ---
_old_infer_music_style_v14 = infer_music_style

def infer_music_style(release_path: Path, meta: dict) -> str:
    text = " ".join([
        str(meta.get("artist", "")),
        str(meta.get("album", "")),
        str(meta.get("release_name", "")),
        str(release_path.name),
    ]).lower()

    if "grateful dead" in text:
        print("Zenei stílus előadó alapján: rock, psychedelic")
        return "rock, psychedelic"

    return _old_infer_music_style_v14(release_path, meta)


# --- multi-disc local tracklist override v16 ---
_old_build_tracklist_from_tags_v16 = build_tracklist_from_tags

def _track_sort_key_v16(path: Path):
    import re

    s = str(path).lower()

    disc = 0
    m = re.search(r"(?:cd|disc|disk)\s*([0-9]+)", s, flags=re.I)
    if m:
        disc = int(m.group(1))

    track = 9999
    # fájlnév eleje: 01, 1-01, 101, 2.01 stb.
    name = path.stem
    m = re.match(r"(?:(\d+)[-. _])?(\d{1,3})", name)
    if m:
        if m.group(1) and disc == 0:
            disc = int(m.group(1))
        track = int(m.group(2))

    return (disc, track, s)


def build_tracklist_from_tags(release_path: Path) -> str:
    import json
    import subprocess

    files = [release_path] if release_path.is_file() else [p for p in release_path.rglob("*") if p.is_file()]
    audio = [p for p in files if p.suffix.lower() in {".flac", ".mp3", ".m4a", ".aac", ".wav"}]
    audio = sorted(audio, key=_track_sort_key_v16)

    if not audio:
        return _old_build_tracklist_from_tags_v16(release_path)

    lines = []
    current_disc = None

    for idx, path in enumerate(audio, start=1):
        try:
            out = subprocess.check_output(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    str(path),
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)
            tags = data.get("format", {}).get("tags", {}) or {}
        except Exception:
            tags = {}

        low = {str(k).lower(): str(v).strip() for k, v in tags.items() if str(v).strip()}

        title = (
            low.get("title")
            or low.get("tracktitle")
            or path.stem
        )

        disc = (
            low.get("discnumber")
            or low.get("disc")
            or ""
        )
        track = (
            low.get("track")
            or low.get("tracknumber")
            or ""
        )

        if "/" in disc:
            disc = disc.split("/", 1)[0]
        if "/" in track:
            track = track.split("/", 1)[0]

        try:
            disc_no = int(disc) if disc else 0
        except Exception:
            disc_no = 0

        try:
            track_no = int(track) if track else idx
        except Exception:
            track_no = idx

        if disc_no and disc_no != current_disc:
            if lines:
                lines.append("")
            lines.append(f"CD{disc_no}")
            current_disc = disc_no

        prefix = f"{track_no:02d}."
        if not disc_no:
            prefix = f"{idx:02d}."

        lines.append(f"{prefix} {title}")

    return "\n".join(lines)


# --- Discogs token robust loader v17 ---
_old_enrich_music_metadata_v17 = enrich_music_metadata

def enrich_music_metadata(meta: dict, discogs_token: str | None = None) -> dict:
    import os

    token = (discogs_token or "").strip()

    if not token:
        try:
            from dotenv import dotenv_values
            env = dotenv_values(".env")
            token = (env.get("DISCOGS_TOKEN") or "").strip()
        except Exception:
            token = ""

    if not token:
        token = (os.getenv("DISCOGS_TOKEN") or "").strip()

    if not token:
        print("Discogs: nincs token, kihagyom.")
        return meta

    return _old_enrich_music_metadata_v17(meta, token)


# --- rules-compliant raw MediaInfo music techinfo v18 ---
def build_music_techinfo(release_path: Path, meta: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{release_path.name}.music.techinfo.txt"

    exts = {".mp3", ".m4a", ".flac", ".ape", ".wav", ".dts", ".mka"}
    files = [release_path] if release_path.is_file() else [p for p in release_path.rglob("*") if p.is_file()]
    audio = sorted([p for p in files if p.suffix.lower() in exts], key=lambda p: str(p).lower())

    lines = []
    lines.append("MediaInfo TEXT output")
    lines.append("=" * 21)
    lines.append("")
    lines.append(f"Release: {release_path.name}")
    lines.append(f"Files: {len(audio)}")
    lines.append("")

    for p in audio:
        lines.append("")
        lines.append("=" * 80)
        try:
            rel = p.relative_to(release_path if release_path.is_dir() else release_path.parent)
        except Exception:
            rel = p
        lines.append(str(rel))
        lines.append("=" * 80)
        try:
            r = subprocess.run(
                ["mediainfo", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            lines.append(r.stdout.strip())
            if r.stderr.strip():
                lines.append("")
                lines.append("MediaInfo stderr:")
                lines.append(r.stderr.strip())
        except Exception as e:
            lines.append(f"MediaInfo error: {e}")

    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out


# --- rules-compliant folder MediaInfo music techinfo v19 ---
def build_music_techinfo(release_path: Path, meta: dict, output_dir: Path) -> Path:
    import subprocess

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{release_path.name}.music.techinfo.txt"

    target = release_path if release_path.exists() else release_path.parent

    try:
        r = subprocess.run(
            ["mediainfo", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        text = r.stdout.strip()
        err = r.stderr.strip()
    except Exception as e:
        text = ""
        err = f"MediaInfo error: {e}"

    lines = []
    lines.append(text)

    if err:
        lines.append("")
        lines.append("MediaInfo stderr:")
        lines.append(err)

    out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return out
