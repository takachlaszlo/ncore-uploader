from __future__ import annotations
from pathlib import Path
from datetime import datetime


def find_nfo(release_path: Path) -> Path | None:
    folder = release_path.parent if release_path.is_file() else release_path
    nfos = list(folder.rglob("*.nfo"))
    if not nfos:
        return None
    root_nfos = [p for p in nfos if p.parent == folder]
    return sorted(root_nfos or nfos)[0]


def build_generated_nfo(meta: dict) -> str:
    lines = [
        "Universal uploader generated NFO",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Name: {meta.get('torrent_name','')}",
        f"Category: {meta.get('category_label','')}",
        f"IMDb: {meta.get('imdb_id','')}",
        f"Artist: {meta.get('artist','')}",
        f"Album: {meta.get('album','')}",
        f"Year: {meta.get('year','') or meta.get('album_year','')}",
        "",
        "Note: This is not an original scene NFO.",
    ]
    return "\n".join(lines).strip() + "\n"


def prepare_nfo(release_path: Path, output_dir: Path, meta: dict) -> tuple[Path, bool]:
    existing = find_nfo(release_path)
    if existing:
        return existing, True
    output_dir.mkdir(parents=True, exist_ok=True)
    nfo_path = output_dir / f"{release_path.name}.generated.nfo"
    nfo_path.write_text(build_generated_nfo(meta), encoding="utf-8")
    return nfo_path, False
