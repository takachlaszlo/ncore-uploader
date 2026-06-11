from __future__ import annotations


def build_spotify_music_queries(meta: dict) -> list[str]:
    artist = (meta.get("artist") or meta.get("előadó") or "").strip()
    album = (meta.get("album") or meta.get("title") or meta.get("cim") or "").strip()
    year = str(meta.get("year") or meta.get("ev") or "").strip()
    release_name = (meta.get("release_name") or meta.get("name") or "").strip()

    queries = []

    # VA / Various Artists release-ek:
    # artist nélkül, album/release cím alapján keressünk
    if release_name.upper().startswith("VA-") or artist.upper() in {"VA", "VARIOUS ARTISTS", "VARIOUS"}:
        cleaned = release_name
        cleaned = re.sub(r"^VA[-_. ]+", "", cleaned, flags=re.I)
        cleaned = re.sub(r"[-_. ]+(WEB|CD|FLAC|MP3|LOSSLESS).*?$", "", cleaned, flags=re.I)
        cleaned = cleaned.replace("_", " ").replace(".", " ").strip()

        if cleaned:
            if year:
                queries.append(f'album:"{cleaned}" year:{year}')
            queries.append(f'album:"{cleaned}"')
            queries.append(cleaned)

        if album:
            if year:
                queries.append(f'album:"{album}" year:{year}')
            queries.append(f'album:"{album}"')

        # Spotifyon sok VA album artistje "Various Artists"
        if album and year:
            queries.append(f'artist:"Various Artists" album:"{album}" year:{year}')
        elif album:
            queries.append(f'artist:"Various Artists" album:"{album}"')

        return [q for q in queries if q.strip()]

    # Normál artist + album keresés
    if artist and album and year:
        queries.append(f'artist:"{artist}" album:"{album}" year:{year}')
    if artist and album:
        queries.append(f'artist:"{artist}" album:"{album}"')
    if album and year:
        queries.append(f'album:"{album}" year:{year}')
    if album:
        queries.append(f'album:"{album}"')

    return [q for q in queries if q.strip()]


from pathlib import Path
import re
import requests


def clean_release_title(name: str) -> dict:
    base = Path(name).stem if "." in Path(name).name else Path(name).name
    year = None

    m = re.search(r"\b(19\d{2}|20\d{2})\b", base)
    if m:
        year = int(m.group(1))
        title = base[:m.start()]
    else:
        title = re.split(
            r"\b(?:S\d{1,2}E\d{1,2}|\d{3,4}p|BluRay|WEB[-.]?DL|REMUX|HDTV|DVDRip|UHD)\b",
            base,
            flags=re.I,
        )[0]

    title = title.replace(".", " ").replace("_", " ").strip(" -")
    season = episode = None

    sm = re.search(r"S(\d{1,2})E(\d{1,2})", base, re.I)
    if sm:
        season, episode = int(sm.group(1)), int(sm.group(2))

    return {
        "title_guess": title,
        "year": year,
        "season": season,
        "episode": episode,
    }


def tmdb_search(meta: dict, api_key: str, is_series: bool = False) -> dict:
    if not api_key:
        return meta

    title = meta.get("title_guess") or ""
    if not title:
        return meta

    media_type = "tv" if is_series else "movie"
    url = f"https://api.themoviedb.org/3/search/{media_type}"

    params = {
        "api_key": api_key,
        "query": title,
        "language": "hu-HU",
        "include_adult": "false",
    }

    if meta.get("year") and not is_series:
        params["year"] = str(meta["year"])
    elif meta.get("year") and is_series:
        params["first_air_date_year"] = str(meta["year"])

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as e:
        print(f"TMDb keresés nem sikerült: {e}")
        return meta

    if not results:
        print("TMDb: nincs találat.")
        return meta

    print("\nTMDb találatok:")
    for i, item in enumerate(results[:8], start=1):
        title_text = item.get("title") or item.get("name") or ""
        original = item.get("original_title") or item.get("original_name") or ""
        date = item.get("release_date") or item.get("first_air_date") or ""
        print(f"{i}. {title_text} / {original} ({date[:4]})")

    choice = input("Választás [Enter = 1, 0 = kihagy]: ").strip()
    if choice == "0":
        return meta
    if not choice:
        choice = "1"

    try:
        selected = results[int(choice) - 1]
    except Exception:
        print("Érvénytelen TMDb választás, kihagyva.")
        return meta

    return tmdb_details(meta, api_key, selected["id"], is_series=is_series)


def tmdb_details(meta: dict, api_key: str, tmdb_id: int, is_series: bool = False) -> dict:
    media_type = "tv" if is_series else "movie"
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"

    params = {
        "api_key": api_key,
        "language": "hu-HU",
        "append_to_response": "credits,external_ids",
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"TMDb részletek nem sikerült: {e}")
        return meta

    ext = data.get("external_ids") or {}
    imdb_id = ext.get("imdb_id")

    if imdb_id:
        meta["imdb_id"] = imdb_id

    if is_series:
        meta["title_hu"] = data.get("name") or meta.get("title_hu")
        meta["title_en"] = data.get("original_name") or meta.get("title_en")
        first_date = data.get("first_air_date") or ""
        if first_date[:4].isdigit():
            meta["year"] = int(first_date[:4])
    else:
        meta["title_hu"] = data.get("title") or meta.get("title_hu")
        meta["title_en"] = data.get("original_title") or meta.get("title_en")
        date = data.get("release_date") or ""
        if date[:4].isdigit():
            meta["year"] = int(date[:4])
        if data.get("runtime"):
            meta["runtime"] = data.get("runtime")

    countries = data.get("production_countries") or []
    if countries:
        meta["country"] = ", ".join(c.get("name", "") for c in countries if c.get("name"))

    credits = data.get("credits") or {}
    crew = credits.get("crew") or []
    cast = credits.get("cast") or []

    directors = [p.get("name") for p in crew if p.get("job") == "Director" and p.get("name")]
    if directors:
        meta["director"] = ", ".join(directors[:3])

    actors = [p.get("name") for p in cast if p.get("name")]
    if actors:
        meta["cast"] = ", ".join(actors[:8])

    if data.get("poster_path"):
        meta["poster_url"] = "https://image.tmdb.org/t/p/w500" + data["poster_path"]

    overview = data.get("overview")
    if overview:
        meta["overview"] = overview

    return meta


def manual_metadata_prompt(meta: dict, is_music: bool = False) -> dict:
    print("\nMetaadatok - Enter = üresen hagy / megtart")
    if is_music:
        for key, label in [
            ("artist", "Előadó"),
            ("album", "Album"),
            ("album_year", "Év"),
            ("music_style", "Stílusok, vesszővel"),
        ]:
            val = input(f"{label} [{meta.get(key,'')}]: ").strip()
            if val:
                meta[key] = val
    else:
        fields = [
            ("imdb_id", "IMDb ID, pl. tt1234567"),
            ("title_hu", "Magyar cím"),
            ("title_en", "Angol/eredeti cím"),
            ("year", "Év"),
            ("country", "Ország"),
            ("runtime", "Hossz perc"),
            ("director", "Rendező"),
            ("cast", "Szereplők"),
        ]

        for key, label in fields:

            # Amit már automatikusan megtaláltunk, azt ne kérdezzük újra.
            if meta.get(key):
                continue

            val = input(f"{label} []: ").strip()
            if val:
                meta[key] = val
    return meta


# --- source detection from release name v1 ---
def infer_video_source_from_name(name: str) -> str:
    import re

    x = str(name or "").replace("_", ".").upper()

    patterns = [
        (r"UHD\.BLURAY|COMPLETE\.UHD|2160P.*UHD.*BLURAY", "UHD BluRay"),
        (r"BLURAY\.REMUX|REMUX", "BluRay REMUX"),
        (r"WEB[-.]DL", "WEB-DL"),
        (r"WEBRIP|WEB[-.]RIP", "WEBRip"),
        (r"\bWEB\b", "WEB"),
        (r"HDTV", "HDTV"),
        (r"BLURAY|BDRIP", "BluRay"),
        (r"DVDR|DVD9|DVD5", "DVD"),
        (r"AMZN|AMAZON", "Amazon"),
        (r"NF|NETFLIX", "Netflix"),
        (r"MAX", "Max"),
        (r"DSNP|DISNEY", "Disney+"),
    ]

    hits = []
    for pat, label in patterns:
        if re.search(pat, x):
            if label not in hits:
                hits.append(label)

    # Ha platform + WEB-DL is van, legyen informatívabb.
    platform = next((h for h in hits if h in {"Amazon", "Netflix", "Max", "Disney+"}), "")
    web = next((h for h in hits if h in {"WEB-DL", "WEBRip", "WEB"}), "")
    if platform and web:
        return f"{platform} {web}"

    return hits[0] if hits else ""
