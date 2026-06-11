from __future__ import annotations

from pathlib import Path
import requests
from PIL import Image


def download_infobar_image(url: str | None, output_dir: Path, name: str = "infobar.jpg") -> Path | None:
    if not url:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / ("raw_" + name)
    final_path = output_dir / name

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        raw_path.write_bytes(r.content)

        img = Image.open(raw_path).convert("RGB")
        img.thumbnail((300, 300))
        img.save(final_path, "JPEG", quality=90)

        raw_path.unlink(missing_ok=True)
        return final_path
    except Exception as e:
        print(f"Infobar kép letöltés/átméretezés nem sikerült: {e}")
        return None


def make_infobar_from_local_image(src_path, output_dir: Path, name: str = "infobar.jpg") -> Path | None:
    src = Path(src_path)
    if not src.exists():
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / name

    try:
        img = Image.open(src).convert("RGB")
        img.thumbnail((300, 300))
        img.save(final_path, "JPEG", quality=90)
        return final_path
    except Exception as e:
        print(f"Helyi infobar kép átméretezése nem sikerült: {e}")
        return None
