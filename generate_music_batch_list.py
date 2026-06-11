#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


AUDIO_EXTS = {".mp3", ".flac"}
DEFAULT_CACHE = "work/music_batch_cache.json"


def load_cache(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_cache(path: Path, items: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(items), indent=2), encoding="utf-8")


def is_music_release(path: Path) -> bool:
    if path.is_file():
        return path.suffix.lower() in AUDIO_EXTS

    if not path.is_dir():
        return False

    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            return True

    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default="/home/accofil/torrents/qbittorrent/music",
        help="qBittorrent root folder",
    )
    ap.add_argument(
        "--output",
        default="work/music_batch_list.txt",
        help="Output list file for batch_upload.py",
    )
    ap.add_argument(
        "--lossless-only",
        action="store_true",
        help="Only include releases containing FLAC",
    )
    ap.add_argument(
        "--mp3-only",
        action="store_true",
        help="Only include releases containing MP3",
    )
    ap.add_argument(
        "--cache",
        default=DEFAULT_CACHE,
        help="Cache file with already listed/processed releases",
    )
    ap.add_argument(
        "--include-cached",
        action="store_true",
        help="Do not skip cached releases",
    )
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    out = Path(args.output)

    if args.lossless_only and args.mp3_only:
        raise SystemExit("Egyszerre nem lehet --lossless-only és --mp3-only.")

    if not root.exists():
        raise SystemExit(f"Nem létező root: {root}")

    cache_path = Path(args.cache)
    cache = load_cache(cache_path)

    releases: list[Path] = []

    for item in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not item.exists():
            continue

        exts = set()

        if item.is_file():
            exts.add(item.suffix.lower())
        elif item.is_dir():
            for p in item.rglob("*"):
                if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                    exts.add(p.suffix.lower())

        if not exts:
            continue

        if args.lossless_only and ".flac" not in exts:
            continue

        if args.mp3_only and ".mp3" not in exts:
            continue

        resolved = str(item.resolve())

        if not args.include_cached and resolved in cache:
            continue

        if exts & AUDIO_EXTS:
            releases.append(item.resolve())

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(str(p) for p in releases) + "\n", encoding="utf-8")

    # Már a listázáskor cache-eljük, hogy ugyanaz ne kerüljön újra listába.
    cache.update(str(p) for p in releases)
    save_cache(cache_path, cache)

    print(f"Talált music release: {len(releases)}")
    print(f"Lista: {out}")

    for p in releases[:30]:
        print(p)

    if len(releases) > 30:
        print(f"... +{len(releases) - 30} további")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
