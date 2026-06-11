from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

MUSIC_CATEGORIES = {"mp3_hun", "mp3", "lossless_hun", "lossless"}
VIDEO_CATEGORIES = {"xvid_hun", "xvid", "dvd_hun", "dvd", "dvd9_hun", "dvd9", "hd_hun", "hd",
                    "xvidser_hun", "xvidser", "dvdser_hun", "dvdser", "hdser_hun", "hdser"}

MP3_MAIN_EXTS = {".mp3", ".m4a"}
LOSSLESS_MAIN_EXTS = {".flac", ".ape", ".wav", ".dts", ".mka"}
MUSIC_COMMON_EXTS = {".m3u", ".sfv", ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".cue", ".log"}
LOSSLESS_EXTRA_EXTS = {".txt", ".iso", ".nrg", ".mds", ".mdf", ".bin"}
FORBIDDEN_PROOF_DOMAINS = {
    "wikipedia.org", "hu.wikipedia.org", "en.wikipedia.org",
    "youtube.com", "www.youtube.com", "youtu.be", "videa.hu",
    "rateyourmusic.com", "www.rateyourmusic.com",
    "music-bazaar.com", "www.music-bazaar.com",
}


def files_under(path: str | Path) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return [x for x in p.rglob("*") if x.is_file()]
    return []


def proof_url(meta: dict, prepared: dict | None = None) -> str:
    prepared = prepared or {}
    return (
        prepared.get("original_proof_url")
        or meta.get("original_proof_url")
        or meta.get("discogs_url")
        or meta.get("amazon_url")
        or meta.get("label_url")
        or meta.get("musicbrainz_url")
        or meta.get("spotify_url")
        or meta.get("imdb_url")
        or meta.get("imdb_id")
        or meta.get("port_url")
        or ""
    )


def is_forbidden_proof_url(url: str) -> bool:
    if not url:
        return False
    if url.startswith("tt") and url[2:].isdigit():
        return False
    host = urlparse(url).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return host in {d[4:] if d.startswith("www.") else d for d in FORBIDDEN_PROOF_DOMAINS}


def sanitize_non_original_name(name: str) -> str:
    x = str(name or "").strip()
    x = re.sub(r"[._]+", " ", x)
    x = re.sub(r"\s+", " ", x)
    x = x.replace(":", " -")
    x = re.sub(r"\s+-\s+", " - ", x)
    return x.strip(" -")


def normalize_music_display_name(meta: dict) -> str:
    artist = str(meta.get("artist", "") or "").strip()
    album = str(meta.get("album", "") or "").strip()

    # 4+ előadó esetén VA.
    parts = re.split(r"\s*(?:,| x | and | & )\s*", artist, flags=re.I)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) > 3:
        artist = "VA"

    artist = artist or "VA" if meta.get("is_va") else artist
    name = f"{artist} - {album}".strip(" -")
    return sanitize_non_original_name(name)


def validate_music_name(meta: dict, torrent_name: str) -> list[str]:
    errors = []
    expected = normalize_music_display_name(meta)
    clean_current = sanitize_non_original_name(torrent_name)

    if not expected or " - " not in expected:
        errors.append("Zenei torrentnév nem állítható elő: hiányzik előadó vagy album.")
    elif clean_current != expected:
        errors.append(f"Zenei nem-original torrentnév normalizálandó: '{clean_current}' -> '{expected}'")

    if re.search(r"\b(MP3|FLAC|WEB-DL|x264|x265|mkv|mp4|avi)\b", clean_current, flags=re.I):
        errors.append("Zenei nem-original torrentnév tiltott technikai kifejezést/fájlkiterjesztést tartalmaz.")

    if any(ch in clean_current for ch in [":", ";", "#"]):
        errors.append("Torrentnév tiltott karaktert tartalmaz (: ; #).")

    return errors


def validate_music_filelist(category: str, release_path: str | Path) -> list[str]:
    errors = []
    files = files_under(release_path)
    exts = {p.suffix.lower() for p in files}

    if category in {"mp3", "mp3_hun"}:
        if not (exts & MP3_MAIN_EXTS):
            errors.append("MP3 kategória: nincs .mp3 vagy .m4a fájl.")
        allowed = MP3_MAIN_EXTS | MUSIC_COMMON_EXTS
        bad = sorted(exts - allowed)
        if bad:
            errors.append("MP3 kategória tiltott fájlkiterjesztések: " + ", ".join(bad))

    if category in {"lossless", "lossless_hun"}:
        if not (exts & LOSSLESS_MAIN_EXTS):
            errors.append("Lossless kategória: nincs .flac/.ape/.wav/.dts/.mka fájl.")
        allowed = LOSSLESS_MAIN_EXTS | MUSIC_COMMON_EXTS | LOSSLESS_EXTRA_EXTS
        bad = sorted(exts - allowed)
        if bad:
            errors.append("Lossless kategória tiltott fájlkiterjesztések: " + ", ".join(bad))

    return errors


def has_text_techinfo(path: str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.exists() or not p.is_file():
        return False
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return "General" in txt and ("Audio" in txt or "Video" in txt or "Format" in txt)


def track_count(tracklist: str) -> int:
    n = 0
    for line in str(tracklist or "").splitlines():
        if re.match(r"^\s*(?:\d{1,3}\.|[A-Z]*\d+\s*$)", line):
            if re.match(r"^\s*\d{1,3}\.\s+\S+", line):
                n += 1
    return n


def build_music_non_original_description(meta: dict, torrent_name: str = "") -> str:
    url = proof_url(meta)
    lines = []

    if torrent_name and len(torrent_name) > 90:
        lines += ["Teljes torrent név:", torrent_name, ""]

    lines += [
        f"Igazoló link: {url}",
        "",
        f"Előadó: {meta.get('artist', '')}",
        f"Album címe: {meta.get('album', '')}",
    ]

    if meta.get("subtitle"):
        lines.append(f"Alcím: {meta.get('subtitle')}")

    lines += [
        f"Megjelenés éve: {meta.get('album_year', '')}",
        "",
        "Számlista:",
    ]

    lines.extend(str(meta.get("tracklist", "") or "").splitlines())
    return "\n".join(lines).strip()


def validate_policy(prepared: dict) -> list[str]:
    errors: list[str] = []

    category = prepared.get("category_value")
    meta = prepared.get("metadata", {}) or {}
    is_original = bool(prepared.get("is_original_release"))
    release_path = prepared.get("release_path") or prepared.get("source_path") or meta.get("source_path") or ""
    torrent_name = prepared.get("torrent_name") or meta.get("torrent_name") or ""

    url = proof_url(meta, prepared)

    if is_original:
        if not prepared.get("nfo_file") or not Path(prepared["nfo_file"]).exists():
            errors.append("Eredeti release: NFO kötelező.")
        return errors

    if not url:
        errors.append("Nem-original release: igazoló/származási link kötelező.")
    elif is_forbidden_proof_url(url):
        errors.append(f"Nem elfogadott igazoló link: {url}")

    if not has_text_techinfo(prepared.get("techinfo_file")):
        errors.append("Nem-original release: MediaInfo TEXT TechInfo kötelező.")

    if category in MUSIC_CATEGORIES:
        ok_img, img_msg = infobar_image_ok(prepared.get("infobar_image"))
        if not ok_img:
            errors.append("Zenei release: " + img_msg)

        for field, label in [
            ("artist", "előadó"),
            ("album", "album címe"),
            ("album_year", "megjelenés éve"),
            ("music_style", "stílus"),
            ("tracklist", "számlista"),
        ]:
            if not meta.get(field):
                errors.append(f"Zenei nem-original release: hiányzik a(z) {label}.")

        if track_count(meta.get("tracklist", "")) < 1:
            errors.append("Zenei nem-original release: a számlista nem tartalmaz felismerhető tracket.")

        if release_path:
            errors.extend(validate_music_filelist(category, release_path))

            if category in {"mp3", "mp3_hun"}:
                ok, msg = mp3_min_bitrate_ok(release_path)
                if not ok:
                    errors.append("MP3 kategória: minimum 128 kbps kötelező. " + msg)

            if category in {"lossless", "lossless_hun"}:
                ok, msg = lossless_txt_files_are_logs(release_path)
                if not ok:
                    errors.append(msg)

        errors.extend(validate_music_name(meta, torrent_name))

    if category in VIDEO_CATEGORIES:
        if not (meta.get("imdb_id") or meta.get("imdb_url") or meta.get("port_url")):
            errors.append("Film/sorozat nem-original: IMDb vagy port.hu igazoló link kötelező.")
        if not meta.get("source"):
            errors.append("Film/sorozat nem-original: forrás megadása kötelező.")
        if not meta.get("audio_tracks"):
            errors.append("Film/sorozat nem-original: hangsávok feltüntetése kötelező.")
        shots = prepared.get("screenshots", []) or []
        if len(shots) != 3:
            errors.append("Film/sorozat nem-original: pontosan 3 mintakép kötelező.")

    return errors


def mp3_min_bitrate_ok(path: str | Path) -> tuple[bool, str]:
    import json
    import subprocess

    for p in files_under(path):
        if p.suffix.lower() not in {".mp3", ".m4a"}:
            continue

        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            data = json.loads(r.stdout or "{}")
            br = int(data.get("format", {}).get("bit_rate") or 0)
            if br and br < 128000:
                return False, f"{p.name}: {br // 1000} kbps"
        except Exception:
            return False, f"{p.name}: bitráta nem ellenőrizhető"

    return True, ""


def lossless_txt_files_are_logs(path: str | Path) -> tuple[bool, str]:
    for p in files_under(path):
        if p.suffix.lower() != ".txt":
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            return False, f"{p.name}: nem olvasható txt"

        log_markers = ["log", "accuraterip", "eac", "xld", "cuetools", "audiochecker"]
        if not any(m in txt for m in log_markers):
            return False, f"{p.name}: Lossless kategóriában a .txt csak log lehet"

    return True, ""


# --- refined lossless txt log validation v2 ---
def lossless_txt_files_are_logs(path: str | Path) -> tuple[bool, str]:
    for p in files_under(path):
        if p.suffix.lower() != ".txt":
            continue

        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            return False, f"{p.name}: nem olvasható txt"

        name = p.name.lower()

        # Elfogadható log-jellegű txt fájlnevek/tartalmak.
        if any(x in name for x in ["log", "eac", "xld", "audiochecker", "accuraterip", "cuetools"]):
            continue

        markers = [
            "exact audio copy",
            "eac extraction logfile",
            "x lossless decoder",
            "xld extraction logfile",
            "accuraterip",
            "cuetools",
            "audiochecker",
            "log created",
            "test crc",
            "copy crc",
            "track quality",
        ]

        if any(m in txt for m in markers):
            continue

        return False, f"{p.name}: Lossless kategóriában .txt csak log lehet"

    return True, ""


def prepare_music_filelist_for_rules(category: str, release_path: str | Path) -> list[str]:
    """
    Szabályzat szerinti automatikus előkészítés:
    Lossless kategóriában a nem log jellegű .txt fájlokat kizárjuk a torrentből.
    Nem töröl, csak áthelyez .excluded_from_ncore_upload alá.
    """
    actions = []

    if category not in {"lossless", "lossless_hun"}:
        return actions

    root = Path(release_path)
    if not root.exists() or not root.is_dir():
        return actions

    excluded = root / ".excluded_from_ncore_upload"
    excluded.mkdir(exist_ok=True)

    for p in list(files_under(root)):
        if p.suffix.lower() != ".txt":
            continue

        ok, msg = lossless_txt_files_are_logs(p.parent)
        # A fenti parent-alapú check több txt-t is láthat, ezért itt direkt ellenőrzünk.
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            txt = ""

        name = p.name.lower()
        markers = [
            "log", "eac", "xld", "audiochecker", "accuraterip", "cuetools",
            "exact audio copy", "eac extraction logfile", "x lossless decoder",
            "xld extraction logfile", "test crc", "copy crc", "track quality",
        ]

        is_log = any(m in name for m in markers) or any(m in txt for m in markers)

        if not is_log:
            target = excluded / p.name
            i = 1
            while target.exists():
                target = excluded / f"{p.stem}.{i}{p.suffix}"
                i += 1
            p.rename(target)
            actions.append(f"Nem log .txt kizárva: {p} -> {target}")

    return actions


# --- safe excluded file mover v3 ---
def prepare_music_filelist_for_rules(category: str, release_path: str | Path) -> list[str]:
    actions = []

    if category not in {"lossless", "lossless_hun"}:
        return actions

    root = Path(release_path)
    if not root.exists() or not root.is_dir():
        return actions

    excluded_root = Path("work/excluded_from_ncore_upload") / root.name
    excluded_root.mkdir(parents=True, exist_ok=True)

    for p in list(files_under(root)):
        if ".excluded_from_ncore_upload" in p.parts:
            continue
        if p.suffix.lower() != ".txt":
            continue

        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            txt = ""

        name = p.name.lower()
        markers = [
            "log", "eac", "xld", "audiochecker", "accuraterip", "cuetools",
            "exact audio copy", "eac extraction logfile", "x lossless decoder",
            "xld extraction logfile", "test crc", "copy crc", "track quality",
        ]

        is_log = any(m in name for m in markers) or any(m in txt for m in markers)

        if not is_log:
            try:
                rel = p.relative_to(root)
            except Exception:
                rel = Path(p.name)

            target = excluded_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)

            i = 1
            final_target = target
            while final_target.exists():
                final_target = target.with_name(f"{target.stem}.{i}{target.suffix}")
                i += 1

            p.rename(final_target)
            actions.append(f"Nem log .txt kizárva a torrentből: {p} -> {final_target}")

    # Ha régi belső excluded mappa maradt, azt is kivisszük.
    old_inside = root / ".excluded_from_ncore_upload"
    if old_inside.exists():
        target = excluded_root / "_previous_internal_excluded"
        i = 1
        final_target = target
        while final_target.exists():
            final_target = excluded_root / f"_previous_internal_excluded.{i}"
            i += 1
        old_inside.rename(final_target)
        actions.append(f"Régi belső excluded mappa kivéve a torrentből: {old_inside} -> {final_target}")

    return actions


def infobar_image_ok(path: str | None) -> tuple[bool, str]:
    if not path:
        return False, "nincs infobar kép"

    p = Path(path)
    if not p.exists():
        return False, "infobar kép nem létezik"

    try:
        from PIL import Image
        with Image.open(p) as img:
            w, h = img.size
        if w > 300 or h > 300:
            return False, f"infobar kép túl nagy: {w}x{h}, maximum 300x300"
    except Exception as e:
        return False, f"infobar kép nem ellenőrizhető: {e}"

    return True, ""


# --- stricter music name sanitizer v4 ---
def sanitize_non_original_name(name: str) -> str:
    x = str(name or "").strip()
    x = x.replace("_", " ")
    x = re.sub(r"\s+", " ", x)
    x = x.replace(":", " -")
    x = x.replace("/", "-")
    x = re.sub(r"\s+-\s+", " - ", x)
    x = re.sub(r"\s*,\s*", ", ", x)
    x = re.sub(r"\s+", " ", x)
    return x.strip(" -")
