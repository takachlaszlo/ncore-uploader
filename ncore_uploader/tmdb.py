

# --- TMDb find by IMDb ID v1 ---
def tmdb_find_by_imdb_id(meta: dict, api_key: str, is_series: bool = False) -> dict:
    import requests

    imdb_id = (meta.get("imdb_id") or "").strip()
    if not imdb_id or not api_key:
        return meta

    try:
        r = requests.get(
            "https://api.themoviedb.org/3/find/" + imdb_id,
            params={
                "api_key": api_key,
                "external_source": "imdb_id",
                "language": "hu-HU",
            },
            timeout=20,
        )
        if r.status_code != 200:
            print(f"TMDb IMDb lookup hiba: HTTP {r.status_code}")
            return meta

        data = r.json()
        items = data.get("tv_results" if is_series else "movie_results", [])
        if not items:
            # fallback: bármelyik találati típus
            items = data.get("tv_results", []) or data.get("movie_results", [])

        if not items:
            print("TMDb IMDb lookup: nincs találat.")
            return meta

        item = items[0]

        title = item.get("name") or item.get("title") or ""
        original = item.get("original_name") or item.get("original_title") or ""
        year_src = item.get("first_air_date") or item.get("release_date") or ""

        if title and not meta.get("title_hu"):
            meta["title_hu"] = title
        if original and not meta.get("title_original"):
            meta["title_original"] = original
        if year_src and not meta.get("year"):
            meta["year"] = year_src[:4]

        if item.get("overview") and not meta.get("plot"):
            meta["plot"] = item["overview"]

        poster = item.get("poster_path")
        if poster and not meta.get("poster_url"):
            meta["poster_url"] = "https://image.tmdb.org/t/p/w500" + poster

        print(f"TMDb IMDb lookup találat: {title or original}")
        return meta

    except Exception as e:
        print(f"TMDb IMDb lookup hiba: {e}")
        return meta


# --- compatibility TMDb title search wrapper ---
def tmdb_search(meta: dict, api_key: str, is_series: bool = False) -> dict:
    import requests
    import re

    if not api_key:
        return meta

    query = (
        meta.get("title_original")
        or meta.get("title_hu")
        or meta.get("title")
        or meta.get("clean_title")
        or meta.get("album")
        or ""
    )

    if not query:
        name = meta.get("torrent_name") or meta.get("release_name") or ""
        query = re.sub(r"[._]+", " ", str(name))
        query = re.sub(r"\bS\d{1,2}(E\d{1,2})?\b", " ", query, flags=re.I)
        query = re.sub(r"\b(720p|1080p|2160p|WEB[- ]?DL|WEBRip|BluRay|H\.?264|H\.?265|x264|x265|GERMAN|ENGLISH|HUN|WAYNE)\b", " ", query, flags=re.I)
        query = re.sub(r"\s+", " ", query).strip()

    if not query:
        print("TMDb: nincs használható keresőkifejezés.")
        return meta

    endpoint = "search/tv" if is_series else "search/movie"

    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/{endpoint}",
            params={
                "api_key": api_key,
                "query": query,
                "language": "hu-HU",
                "include_adult": "false",
            },
            timeout=20,
        )

        if r.status_code != 200:
            print(f"TMDb keresés hiba: HTTP {r.status_code}")
            return meta

        data = r.json()
        results = data.get("results", [])
        if not results:
            print("TMDb: nincs találat.")
            return meta

        item = results[0]

        title = item.get("name") or item.get("title") or ""
        original = item.get("original_name") or item.get("original_title") or ""
        year_src = item.get("first_air_date") or item.get("release_date") or ""

        if title and not meta.get("title_hu"):
            meta["title_hu"] = title
        if original and not meta.get("title_original"):
            meta["title_original"] = original
        if year_src and not meta.get("year"):
            meta["year"] = year_src[:4]
        if item.get("overview") and not meta.get("plot"):
            meta["plot"] = item["overview"]
        if item.get("poster_path") and not meta.get("poster_url"):
            meta["poster_url"] = "https://image.tmdb.org/t/p/w500" + item["poster_path"]

        print(f"TMDb találat: {title or original}")
        return meta

    except Exception as e:
        print(f"TMDb keresés hiba: {e}")
        return meta
