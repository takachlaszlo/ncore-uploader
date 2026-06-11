from __future__ import annotations

from pathlib import Path
from playwright.sync_api import sync_playwright, Page


def set_if(page: Page, selector: str, value):
    if value is not None and str(value).strip():
        page.fill(selector, str(value))


def upload_file_if_exists(page: Page, selector: str, file_path: str | None):
    if not file_path:
        return
    p = Path(file_path)
    if p.exists():
        page.set_input_files(selector, str(p))
    else:
        print(f"Figyelem: fájl nem létezik, kihagyva: {p}")


def upload_to_ncore_form(
    prepared: dict,
    upload_url: str,
    profile_dir: Path,
    accept_rules: bool = False,
    accept_seed: bool = False,
):
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
        )
        page = browser.new_page()
        page.goto(upload_url, wait_until="domcontentloaded")
        page.wait_for_selector("#torr_tipus", timeout=30000)

        page.select_option("#torr_tipus", prepared["category_value"])
        page.fill("#torrent_nev", prepared["torrent_name"])

        if prepared["is_original_release"]:
            page.check("#eredeti_igen")
        else:
            page.check("#eredeti_nem")

        page.evaluate("lapoz('1','2')")
        page.wait_for_selector("#torrent_fajl", state="attached", timeout=10000)

        upload_file_if_exists(page, "#torrent_fajl", prepared.get("torrent_file"))

        if prepared.get("nfo_file") and prepared["is_original_release"]:
            upload_file_if_exists(page, "#nfo_fajl", prepared.get("nfo_file"))

        if prepared.get("techinfo_file") and not prepared["is_original_release"]:
            upload_file_if_exists(page, "#techinfo_fajl", prepared.get("techinfo_file"))

        page.evaluate("lapoz('2','3')")
        page.wait_for_selector("#szoveg", state="attached", timeout=10000)

        meta = prepared.get("metadata", {})

        set_if(page, "#imdb_orig_results_id", meta.get("imdb_id"))
        set_if(page, "#film_adatbazis", meta.get("film_database"))
        set_if(page, "#megjelenes_eve", meta.get("year"))
        set_if(page, "#orszag", meta.get("country"))
        set_if(page, "#hossz", meta.get("runtime"))
        set_if(page, "#magyar_cim", meta.get("title_hu"))
        set_if(page, "#angol_cim", meta.get("title_en"))
        set_if(page, "#rendezo", meta.get("director"))
        set_if(page, "#szereplok", meta.get("cast"))

        if meta.get("season") is not None:
            page.select_option("select[name='szezon']", str(meta["season"]))

        if meta.get("episode") is not None:
            set_if(page, "input[name='epizod_szamok']", str(meta["episode"]))

        set_if(page, "input[name='epizod_cim']", meta.get("episode_title"))
        set_if(page, "#film_hangsav", meta.get("audio_tracks"))
        set_if(page, "#film_felirat", meta.get("subtitles"))
        set_if(page, "#film_extra", meta.get("extras"))

        set_if(page, "#zene_eloado", meta.get("artist"))
        set_if(page, "#zene_cim", meta.get("album"))
        set_if(page, "#zene_megjelenes", meta.get("album_year"))
        set_if(page, "#music_style", meta.get("music_style"))

        upload_file_if_exists(page, "#infobar_kep", prepared.get("infobar_image"))

        page.evaluate("lapoz('3','4')")
        page.wait_for_selector("#szoveg", state="attached", timeout=10000)

        set_if(page, "#szoveg", prepared.get("description"))

        shots = prepared.get("screenshots", [])
        for idx, selector in enumerate(["#kep1", "#kep2", "#kep3"]):
            if idx < len(shots):
                upload_file_if_exists(page, selector, shots[idx])

        if accept_rules:
            page.check("#mindent_tud1")
        if accept_seed:
            page.check("#mindent_tud3")

        print("\nAz nCore űrlapot kitöltöttem.")
        print("Ellenőrizd kézzel, és csak utána küldd be az oldalon.")
        input("Nyomj Entert itt, ha bezárhatom a böngészőt...")

        browser.close()
