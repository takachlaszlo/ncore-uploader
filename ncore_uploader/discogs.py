from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


DISCOGS_API = "https://api.discogs.com"


@dataclass
class DiscogsResult:
    title: str
    year: str
    country: str
    uri: str
    cover_image: str
    genre: list[str]
    style: list[str]
    release_id: int | None


def headers() -> dict[str, str]:
    load_dotenv()
    token = os.getenv("DISCOGS_TOKEN", "").strip()

    h = {
        "User-Agent": "ncore-universal-uploader/0.2",
    }

    if token:
        h["Authorization"] = f"Discogs token={token}"

    return h


def print_rate_limit(resp: requests.Response) -> None:
    remaining = resp.headers.get("X-Discogs-Ratelimit-Remaining")
    limit = resp.headers.get("X-Discogs-Ratelimit")
    used = resp.headers.get("X-Discogs-Ratelimit-Used")

    if remaining is not None:
        print(f"Discogs rate limit: {remaining}/{limit} remaining, used={used}")


def search_release(artist: str, album: str, barcode: str = "") -> list[DiscogsResult]:
    params: dict[str, Any] = {
        "type": "release",
        "per_page": 5,
        "page": 1,
    }

    if barcode:
        params["barcode"] = barcode
    else:
        params["q"] = f"{artist} {album}".strip()

    resp = requests.get(
        f"{DISCOGS_API}/database/search",
        params=params,
        headers=headers(),
        timeout=30,
    )

    print_rate_limit(resp)

    if resp.status_code == 429:
        raise RuntimeError("Discogs rate limit elérve. Próbáld később.")

    resp.raise_for_status()
    data = resp.json()

    out: list[DiscogsResult] = []

    for item in data.get("results", []):
        out.append(
            DiscogsResult(
                title=item.get("title", ""),
                year=str(item.get("year", "")),
                country=item.get("country", ""),
                uri=item.get("uri", ""),
                cover_image=item.get("cover_image", ""),
                genre=item.get("genre") or [],
                style=item.get("style") or [],
                release_id=item.get("id"),
            )
        )

    return out


def main() -> None:
    if len(sys.argv) < 3:
        print('Használat: python -m ncore_uploader.discogs "Artist" "Album" ["Barcode"]')
        raise SystemExit(1)

    artist = sys.argv[1]
    album = sys.argv[2]
    barcode = sys.argv[3] if len(sys.argv) > 3 else ""

    results = search_release(artist, album, barcode)

    if not results and barcode:
        print("Nincs találat barcode alapján, próbálom előadó + cím alapján...")
        results = search_release(artist, album, "")

    if not results:
        print("Nincs Discogs találat.")
        return

    for i, r in enumerate(results, start=1):
        print("")
        print(f"{i}. {r.title}")
        print(f"   Year: {r.year}")
        print(f"   Country: {r.country}")
        print(f"   URL: https://www.discogs.com{r.uri}")
        print(f"   Genre: {', '.join(r.genre)}")
        print(f"   Style: {', '.join(r.style)}")
        print(f"   Cover: {r.cover_image}")


if __name__ == "__main__":
    main()
