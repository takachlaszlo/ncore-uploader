from __future__ import annotations

from pathlib import Path
import os
import requests
from dotenv import load_dotenv


def qbit_session() -> tuple[requests.Session, str]:
    load_dotenv()

    base_url = os.getenv("QB_URL", "").rstrip("/")
    user = os.getenv("QB_USER", "")
    password = os.getenv("QB_PASS", "")

    if not base_url or not user or not password:
        raise RuntimeError("Hiányzó QB_URL/QB_USER/QB_PASS a .env fájlban.")

    s = requests.Session()
    r = s.post(
        f"{base_url}/api/v2/auth/login",
        data={"username": user, "password": password},
        timeout=20,
    )

    if r.text.strip() != "Ok.":
        raise RuntimeError(f"qBittorrent login sikertelen: HTTP {r.status_code}, {r.text[:100]}")

    return s, base_url


def add_torrent_for_seeding(torrent_file: str, save_path: str, category: str | None = None) -> bool:
    s, base_url = qbit_session()

    p = Path(torrent_file)
    if not p.exists():
        raise FileNotFoundError(p)

    data = {
        "savepath": save_path,
        "skip_checking": "false",
        "paused": "false",
    }

    if category:
        data["category"] = category

    with p.open("rb") as f:
        files = {
            "torrents": (p.name, f, "application/x-bittorrent")
        }
        r = s.post(
            f"{base_url}/api/v2/torrents/add",
            data=data,
            files=files,
            timeout=60,
        )

    if r.status_code != 200:
        raise RuntimeError(f"qBittorrent add hiba: HTTP {r.status_code}, {r.text[:300]}")

    print(f"qBittorrentbe hozzáadva: {p.name}")
    print(f"Save path: {save_path}")
    return True
