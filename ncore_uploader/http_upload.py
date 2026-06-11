from __future__ import annotations

from http.cookiejar import MozillaCookieJar
from pathlib import Path
import re
import requests


def load_session(cookie_file: str = "auth/ncore.txt") -> requests.Session:
    jar = MozillaCookieJar(cookie_file)
    jar.load(ignore_discard=True, ignore_expires=True)

    s = requests.Session()
    s.cookies = jar
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://ncore.pro/upload.php",
    })
    return s


def extract_get_unique(html: str) -> str:
    m = re.search(r'name="getUnique"\s+value="([^"]+)"', html)
    if not m:
        raise RuntimeError("Nem találtam getUnique hidden mezőt az upload oldalon.")
    return m.group(1)


def open_file(path: str | None):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return open(p, "rb")


def build_upload_payload(prepared: dict, get_unique: str):
    meta = prepared.get("metadata", {})

    data = {
        "getUnique": get_unique,
        "tipus": prepared["category_value"],
        "torrent_nev": prepared["torrent_name"],
        "eredeti": "igen" if prepared["is_original_release"] else "nem",
        "szoveg": prepared.get("description", ""),
        "keresre": "nem",
        "mindent_tud1": "szabalyzat",
        "mindent_tud3": "seedeles",
        "submit": "submit",
    }

    # Zenei kategóriánál a stílus kötelező eredeti release esetén is.
    if prepared["category_value"] in {"mp3_hun", "mp3", "lossless_hun", "lossless", "clip"}:
        data["music_style"] = meta.get("music_style") or ""

    # Eredeti release esetén ne küldjünk extra infobar mezőket,
    # mert az nCore külön megjeleníti őket az adatlapon.
    if not prepared["is_original_release"]:
        data.update({
            "imdb_id": meta.get("imdb_id") or "",
            "film_adatbazis": meta.get("film_database") or "",
            "megjelent": str(meta.get("year") or ""),
            "orszag": meta.get("country") or "",
            "hossz": str(meta.get("runtime") or ""),
            "film_magyar_cim": meta.get("title_hu") or "",
            "film_angol_cim": meta.get("title_en") or "",
            "film_idegen_cim": meta.get("title_en") or "",
            "rendezo": meta.get("director") or "",
            "szereplok": meta.get("cast") or "",

            "szezon": str(meta.get("season") or ""),
            "epizod_szamok": str(meta.get("episode") or ""),
            "epizod_cim": meta.get("episode_title") or "",

            "film_hangsav": meta.get("audio_tracks") or "",
            "film_felirat": meta.get("subtitles") or "",
            "film_extra": meta.get("extras") or "",

            "eloado": meta.get("artist") or "",
            "album": meta.get("album") or "",
            "album_megjelenes": str(meta.get("album_year") or ""),
            "music_style": meta.get("music_style") or "",
        })

    files = {}

    torrent_f = open_file(prepared.get("torrent_file"))
    if torrent_f:
        files["torrent_fajl"] = (Path(prepared["torrent_file"]).name, torrent_f)

    is_music = prepared["category_value"] in {"mp3_hun", "mp3", "lossless_hun", "lossless", "clip"}

    nfo_f = open_file(prepared.get("nfo_file"))
    if nfo_f:
        files["nfo_fajl"] = (Path(prepared["nfo_file"]).name, nfo_f)

    tech_f = open_file(prepared.get("techinfo_file"))
    if tech_f:
        files["techinfo_fajl"] = (Path(prepared["techinfo_file"]).name, tech_f)

    infobar_f = open_file(prepared.get("infobar_image"))
    if infobar_f:
        files["infobar_kep"] = (Path(prepared["infobar_image"]).name, infobar_f)

    for i, shot in enumerate(prepared.get("screenshots", [])[:3], start=1):
        f = open_file(shot)
        if f:
            files[f"kep{i}"] = (Path(shot).name, f)

    return data, files


def close_files(files: dict):
    for item in files.values():
        try:
            item[1].close()
        except Exception:
            pass


def upload_http(prepared: dict, upload_url: str, cookie_file: str = "auth/ncore.txt", submit: bool = False):
    s = load_session(cookie_file)

    r = s.get(upload_url, allow_redirects=True, timeout=30)
    if "login.php" in r.url or 'id="feltoltes"' not in r.text:
        raise RuntimeError("Nem vagy belépve, vagy nem elérhető az upload form.")

    get_unique = extract_get_unique(r.text)
    data, files = build_upload_payload(prepared, get_unique)
    data = add_original_proof_to_data(data, prepared)

    print("\nHTTP upload előnézet:")
    print(f"URL: {upload_url}")
    print(f"Kategória: {data['tipus']}")
    print(f"Név: {data['torrent_nev']}")
    print(f"Eredeti: {data['eredeti']}")
    print(f"Fájlmezők: {', '.join(files.keys())}")

    if not submit:
        close_files(files)
        print("\nNem küldtem be. HTTP feltöltéshez futtasd --submit kapcsolóval.")
        return None

    confirm = input("\nFeltöltés indítása? [Enter=igen, n=nem]\n> ").strip().lower()
    if confirm in {"n", "no", "nem"}:
        close_files(files)
        print("Megszakítva, nem küldtem be.")
        return None

    try:
        resp = s.post(upload_url, data=data, files=files, allow_redirects=True, timeout=120)
        print("HTTP:", resp.status_code)
        print("Végső URL:", resp.url)
        print("Válasz hossza:", len(resp.text))

        out = Path("work/last_upload_response.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(resp.text, encoding="utf-8", errors="ignore")
        print(f"Válasz mentve: {out}")

        safe_name = str(prepared.get("torrent_name", "unknown")).replace("/", "_")
        archive_dir = Path("work/upload_responses")
        archive_dir.mkdir(parents=True, exist_ok=True)
        archived = archive_dir / f"{safe_name}.html"
        archived.write_text(resp.text, encoding="utf-8", errors="ignore")

        errors = extract_upload_errors(resp.text)
        if errors:
            errlog = Path("work/upload_errors.log")
            with errlog.open("a", encoding="utf-8") as f:
                f.write(f"\n=== {prepared.get('torrent_name', 'unknown')} ===\n")
                f.write(f"HTML: {archived}\n")
                for err in errors:
                    f.write(f"- Hiba: {err}\n")
                    f.write(f"  Javaslat: {suggest_upload_fix(err)}\n")
            print("Feltöltési hiba(k):")
            for err in errors:
                print(f"- {err}")
                print(f"  {suggest_upload_fix(err)}")

        torrent_id = extract_uploaded_torrent_id(resp.text)
        if torrent_id:
            print(f"Feltöltött torrent ID: {torrent_id}")
        else:
            print("Figyelem: nem találtam feltöltött torrent ID-t.")

        return resp
    finally:
        close_files(files)


def extract_uploaded_torrent_id(html: str) -> str | None:
    import re
    patterns = [
        r'torrents\.php\?action=details&id=([0-9]+)',
        r'torrents\.php\?action=download&id=([0-9]+)',
        r"getNfo\('nfocontent',\s*'([0-9]+)'",
        r"peers\('peers',\s*'([0-9]+)'",
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def extract_download_url(html: str, base_url: str = "https://ncore.pro") -> str | None:
    import re

    m = re.search(r'torrents\.php\?action=download&id=\d+&key=[a-f0-9]+', html)
    if not m:
        return None

    return f"{base_url}/{m.group(0)}"


def download_uploaded_torrent(
    html: str,
    cookie_file: str = "auth/ncore.txt",
    output_dir: str = "work/downloaded_torrents",
) -> str | None:
    from pathlib import Path

    url = extract_download_url(html)
    if not url:
        url = build_download_url_from_id_and_key(html)

    if not url:
        print("Nem találtam letöltőlinket és ID+key párost sem.")
        return None

    s = load_session(cookie_file)
    r = s.get(url, allow_redirects=True, timeout=30)

    if r.status_code != 200 or not r.content.startswith(b"d8:announce"):
        print(f"Torrent letöltés nem sikerült: HTTP {r.status_code}, type={r.headers.get('Content-Type')}")
        return None

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    torrent_id = extract_uploaded_torrent_id(html) or "uploaded"
    out = out_dir / f"ncore_{torrent_id}.torrent"
    out.write_bytes(r.content)

    print(f"nCore torrent letöltve: {out}")
    return str(out)


def build_download_url_from_id_and_key(html: str, base_url: str = "https://ncore.pro") -> str | None:
    torrent_id = extract_uploaded_torrent_id(html)
    key = extract_rss_key(html)
    if not torrent_id or not key:
        return None
    return f"{base_url}/torrents.php?action=download&id={torrent_id}&key={key}"


# --- upload success detection v1 ---
def upload_response_has_error(html: str) -> bool:
    bad_markers = [
        "A felvitelnél néhány hiba történt",
        "A feltöltött torrent már létezik",
        "Hiba!",
        "doboz_error",
        "box_error",
    ]
    return any(x in html for x in bad_markers)


def upload_response_successful(html: str) -> bool:
    if upload_response_has_error(html):
        return False
    return extract_uploaded_torrent_id(html) is not None


def extract_rss_key(html: str) -> str | None:
    import re

    m = re.search(r"rss\.php\?key=([a-f0-9]+)", html)
    return m.group(1) if m else None


def build_download_url_from_id_and_key(html: str, base_url: str = "https://ncore.pro") -> str | None:
    torrent_id = extract_uploaded_torrent_id(html)
    key = extract_rss_key(html)

    if not torrent_id or not key:
        return None

    return f"{base_url}/torrents.php?action=download&id={torrent_id}&key={key}"


def upload_response_has_error(html: str) -> bool:
    bad_markers = [
        "A felvitelnél néhány hiba történt",
        "A feltöltött torrent már létezik",
        "Hiba!",
        "doboz_error",
        "box_error",
    ]
    return any(x in html for x in bad_markers)


def upload_response_successful(html: str) -> bool:
    if upload_response_has_error(html):
        return False
    return extract_uploaded_torrent_id(html) is not None


def add_original_proof_to_data(data: dict, prepared: dict) -> dict:
    meta = prepared.get("metadata", {}) or {}

    proof = (
        prepared.get("original_proof_url")
        or meta.get("spotify_url")
        or meta.get("discogs_url")
        or meta.get("musicbrainz_url")
        or ""
    )

    if proof:
        data["eredeti_valami"] = proof

    return data


def extract_upload_errors(html: str) -> list[str]:
    import re
    from html import unescape

    errors = []

    # Dupe hiba: ez önmagában elég, ne logoljuk mellé a form súgó <li>-jeit.
    m = re.search(r"A feltöltött torrent már létezik(?::\s*([^<\n]+))?", html, flags=re.I)
    if m:
        name = (m.group(1) or "").strip()
        if name:
            return [f"A feltöltött torrent már létezik: {name}"]
        return ["A feltöltött torrent már létezik"]

    # Csak a tényleges hiba panelből olvasunk:
    # "A felvitelnél néhány hiba történt:" utáni első <ul>...</ul>
    m = re.search(
        r"A felvitelnél néhány hiba történt:.*?<ul>(.*?)</ul>",
        html,
        flags=re.I | re.S,
    )

    if m:
        block = m.group(1)
        for li in re.finditer(r"<li>(.*?)</li>", block, flags=re.I | re.S):
            text = re.sub(r"<.*?>", "", li.group(1))
            text = unescape(text).strip()
            if text and text not in errors:
                errors.append(text)

    return errors


def suggest_upload_fix(error: str) -> str:
    e = error.lower()

    if "stílus" in e or "stilus" in e:
        return "Javítás: music_style üres volt. Ellenőrizd az NFO Genre/Style sort, vagy bővítsd az NFO genre → nCore tag normalizálást."
    if "már létezik" in e or "dupe" in e:
        return "Javítás: dupe. Hagyd ki a release-t, vagy ellenőrizd manuálisan az nCore találatot."
    if "nfo" in e:
        return "Javítás: ellenőrizd, hogy eredeti release esetén tényleg van .nfo és fel lett csatolva."
    if "torrent" in e:
        return "Javítás: ellenőrizd a generált .torrent fájlt és a tracker/passkey beállítást."
    if "kép" in e or "infobar" in e:
        return "Javítás: ellenőrizd az infobar képet; legyen létező JPG/PNG és megfelelő méretű."

    return "Javaslat: nézd meg az adott mentett HTML választ a work/upload_responses mappában."
