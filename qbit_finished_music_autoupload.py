#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
LOG = BASE / "work" / "qbit_auto_upload.log"
STATE = BASE / "work" / "qbit_auto_upload_state.json"
AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".ape", ".wav", ".dts", ".mka"}
VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".vob", ".iso"}



def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line)
    LOG.open("a", encoding="utf-8").write(line + "\n")


def load_state() -> set[str]:
    if not STATE.exists():
        return set()
    try:
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_state(items: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(items), indent=2), encoding="utf-8")


def files_under(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return [p for p in path.rglob("*") if p.is_file()]
    return []


def find_release_path(args: list[str]) -> Path | None:
    # qBit javasolt argumentumok:
    # argv[1] = %F content path
    # argv[2] = %N torrent name
    # argv[3] = %R save path/root
    content = Path(args[1]).expanduser() if len(args) > 1 and args[1] else None
    name = args[2] if len(args) > 2 else ""
    root = Path(args[3]).expanduser() if len(args) > 3 and args[3] else None

    candidates: list[Path] = []

    if content:
        candidates.append(content)

        # Ha %F egy fájl, akkor a release a parent lehet.
        if content.is_file():
            candidates.append(content.parent)

    if root and name:
        candidates.append(root / name)

    if content and name:
        candidates.append(content / name)

    for c in candidates:
        try:
            r = c.resolve()
        except Exception:
            r = c
        if r.exists():
            return r

    return None


def has_music_tag(args: list[str]) -> bool:
    # qBit argv[4] = %L labels/tags, pl. "music" vagy "music,scene"
    tags_raw = args[4] if len(args) > 4 else ""
    tags = {
        t.strip().lower()
        for t in str(tags_raw).replace(";", ",").split(",")
        if t.strip()
    }
    return "music" in tags


def infer_category(path: Path) -> str | None:
    exts = {p.suffix.lower() for p in files_under(path)}
    if ".flac" in exts:
        return "18"
    if ".mp3" in exts:
        return "16"
    return None


def has_nfo(path: Path) -> bool:
    return any(p.suffix.lower() == ".nfo" for p in files_under(path))


def has_video_files(path: Path) -> bool:
    return any(p.suffix.lower() in VIDEO_EXTS for p in files_under(path))


def is_probably_scene_music_release(path: Path) -> bool:
    files = files_under(path)
    exts = {p.suffix.lower() for p in files}

    if not (exts & AUDIO_EXTS):
        return False

    if has_video_files(path):
        return False

    if not has_nfo(path):
        return False

    # Scene zenei release-ekben tipikusan van NFO és zenei release tag a névben.
    name = path.name.upper()
    music_markers = [
        "WEB", "CD", "CDR", "CDM", "SINGLE", "EP", "FLAC", "MP3",
        "24BIT", "16BIT", "VINYL", "PROMO", "OST"
    ]

    return any(m in name for m in music_markers)


def main() -> int:
    log("HOOK CALLED: argv=" + repr(sys.argv))

    if not has_music_tag(sys.argv):
        log("SKIP: nincs music qBit tag, nem zenei autoupload")
        return 0

    release = find_release_path(sys.argv)
    if not release:
        log("SKIP: nem sikerült release útvonalat találni az argumentumokból")
        return 0

    log(f"RELEASE PATH: {release}")

    category = infer_category(release)
    if not category:
        log(f"SKIP: nem MP3/FLAC/Lossless release: {release}")
        return 0

    if has_video_files(release):
        log(f"SKIP: videófájlt tartalmaz, nem zenei autoupload: {release}")
        return 0

    if not has_nfo(release):
        log(f"SKIP: nincs .nfo, nem automata scene zenei release: {release}")
        return 0

    if not is_probably_scene_music_release(release):
        log(f"SKIP: nem tűnik scene zenei release-nek: {release}")
        return 0

    state = load_state()
    key = str(release.resolve())

    if key in state:
        log(f"SKIP: már feldolgozott: {release}")
        return 0

    stdin_text = category + "\n\n\n\n\n\n"

    cmd = [
        "/home/accofil/venv/bin/python",
        str(BASE / "uploader.py"),
        "--submit",
        str(release),
    ]

    log("START UPLOAD: " + " ".join(cmd))

    proc = subprocess.run(
        cmd,
        cwd=str(BASE),
        input=stdin_text,
        text=True,
        capture_output=True,
    )

    LOG.open("a", encoding="utf-8").write("\n--- UPLOADER STDOUT ---\n" + proc.stdout)
    LOG.open("a", encoding="utf-8").write("\n--- UPLOADER STDERR ---\n" + proc.stderr)

    log(f"UPLOADER EXIT: {proc.returncode}")

    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")

    if proc.returncode == 0 and "READY TO UPLOAD" in combined and "Feltöltés nem volt sikeres" not in combined:
        state.add(key)
        save_state(state)
        log(f"SUCCESS: state-be mentve: {release}")
    else:
        log(f"FAILED: nem kerül state-be, újra próbálható: {release}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
