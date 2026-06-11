from __future__ import annotations

from pathlib import Path
import subprocess
import yaml


def create_torrent(release_path: Path, output_dir: Path, config_path: str = "config.yaml") -> Path:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    announce_url = cfg.get("torrent", {}).get("announce_url", "https://example.invalid/announce")

    output_dir.mkdir(parents=True, exist_ok=True)

    out = output_dir / f"{release_path.name}.torrent"

    if out.exists():
        out.unlink()

    subprocess.run(
        [
            "mktorrent",
            "-p",
            "-a", announce_url,
            "-o", str(out),
            str(release_path),
        ],
        check=True,
    )

    return out
