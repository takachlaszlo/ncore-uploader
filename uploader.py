from __future__ import annotations

from pathlib import Path
import argparse
import os
import yaml

from ncore_uploader.schema import NCORE_CATEGORIES, VIDEO_CATEGORIES, MUSIC_CATEGORIES
from ncore_uploader.metadata import (
    clean_release_title,
    manual_metadata_prompt,
    infer_video_source_from_name,
)
from ncore_uploader.images import download_infobar_image, make_infobar_from_local_image
from ncore_uploader.nfo import prepare_nfo
from ncore_uploader.tmdb import tmdb_search, tmdb_find_by_imdb_id
from ncore_uploader.media import (
    first_media_file,
    mediainfo_text,
    extract_audio_subtitle_summary,
    generate_screenshots,
    VIDEO_EXTS,
)
from ncore_uploader.torrent import create_torrent
from ncore_uploader.music import (
    parse_music_release,
    infer_music_style,
    find_local_cover,
    musicbrainz_cover_url,
    cover_url_from_nfo,
    build_music_generated_nfo,
    build_tracklist_from_tags,
    build_music_techinfo,
    enrich_music_from_audio_tags,
    musicbrainz_enrich_metadata,
    enrich_music_metadata,
    apply_manual_music_url,
)
from ncore_uploader.http_upload import upload_http, download_uploaded_torrent, upload_response_successful
from ncore_uploader.validate import validate_prepared
from ncore_uploader.spotify import enrich_music_with_spotify
from ncore_uploader.qbit import add_torrent_for_seeding
from ncore_uploader.policy import build_music_non_original_description, normalize_music_display_name, prepare_music_filelist_for_rules


SERIES_CATEGORIES = {"xvidser_hun", "xvidser", "dvdser_hun", "dvdser", "hdser_hun", "hdser"}


import re
from html import unescape

def parse_ncore_upload_result(html: str):
    if "A felvitelnél néhány hiba történt" in html or "A feltöltött torrent már létezik" in html:
        m = re.search(
            r'A feltöltött torrent már létezik:\s*<a href="torrents\.php\?action=details&id=(\d+)">([^<]+)</a>',
            html,
            re.I | re.S,
        )
        if m:
            return {
                "ok": False,
                "duplicate": True,
                "id": m.group(1),
                "name": unescape(m.group(2)),
                "url": f"https://ncore.pro/torrents.php?action=details&id={m.group(1)}",
            }
        return {"ok": False, "duplicate": False, "error": "nCore hibát jelzett a feltöltésnél."}

    m = re.search(r'torrents\.php\?action=details&id=(\d+)', html)
    if m:
        return {
            "ok": True,
            "duplicate": False,
            "id": m.group(1),
            "url": f"https://ncore.pro/torrents.php?action=details&id={m.group(1)}",
        }

    return {"ok": False, "duplicate": False, "error": "Nem sikerült torrent ID-t kinyerni."}


def choose_category() -> tuple[str, str]:
    print("\nKategória:")
    for key, (label, value) in NCORE_CATEGORIES.items():
        print(f"{key:>2} - {label}")

    while True:
        choice = input("\nVálasztás: ").strip()
        if choice in NCORE_CATEGORIES:
            return NCORE_CATEGORIES[choice]
        print("Érvénytelen választás.")


def best_original_proof_url(meta: dict) -> str:
    return (
        meta.get("spotify_url")
        or meta.get("discogs_url")
        or meta.get("musicbrainz_url")
        or ""
    )


def build_description(prepared: dict) -> str:
    meta = prepared.get("metadata", {})
    category_value = prepared.get("category_value", "")
    is_music = category_value in MUSIC_CATEGORIES
    is_series = category_value in SERIES_CATEGORIES

    if prepared.get("is_original_release"):
        return ""

    lines: list[str] = []

    if is_music:
        if meta.get("artist"):
            lines.append(f"Előadó: {meta['artist']}")
        if meta.get("album"):
            lines.append(f"Album: {meta['album']}")
        if meta.get("album_year"):
            lines.append(f"Év: {meta['album_year']}")
        if meta.get("music_style"):
            lines.append(f"Stílus: {meta['music_style']}")

        if meta.get("tracklist"):
            lines.append("")
            lines.append("Tracklist:")
            lines.append(str(meta["tracklist"]))

        if meta.get("spotify_url"):
            lines.append("")
            lines.append(f"Spotify: {meta['spotify_url']}")

        if meta.get("discogs_url"):
            lines.append("")
            lines.append(f"Discogs: {meta['discogs_url']}")
        elif meta.get("musicbrainz_url"):
            lines.append("")
            lines.append(f"MusicBrainz: {meta['musicbrainz_url']}")

        return "\n".join(lines)

    if meta.get("subtitles"):
        lines.append(f"Felirat(ok): {meta['subtitles']}")

    if meta.get("audio_tracks"):
        lines.append(f"Hangsáv(ok): {meta['audio_tracks']}")

    if is_series and meta.get("season") is not None:
        lines.append(f"Évad: {meta['season']}")

    if is_series and meta.get("episode") is not None:
        lines.append(f"Epizód: {meta['episode']}")

    return "\n".join(lines)


def prepare(args) -> tuple[dict, dict]:
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    release_path = Path(args.release).expanduser().resolve()
    if not release_path.exists():
        raise SystemExit(f"Nem létező release útvonal: {release_path}")

    category_label, category_value = choose_category()

    meta = clean_release_title(release_path.name)
    meta["torrent_name"] = release_path.name
    meta["category_label"] = category_label

    media_file = first_media_file(release_path)

    if media_file and media_file.suffix.lower() in VIDEO_EXTS:
        try:
            audio, subs = extract_audio_subtitle_summary(media_file)
            meta["audio_tracks"] = audio
            meta["subtitles"] = subs
        except Exception as e:
            print(f"MediaInfo/ffprobe összegzés nem sikerült: {e}")

    is_music = category_value in MUSIC_CATEGORIES
    is_series = category_value in SERIES_CATEGORIES
    is_video_meta = category_value in VIDEO_CATEGORIES

    if is_video_meta and not meta.get("source"):
        src = infer_video_source_from_name(release_path.name)
        if src:
            meta["source"] = src
            print(f"Forrás felismerve release névből: {src}")

    if is_music:
        music_meta = parse_music_release(release_path.name)
        meta.update({k: v for k, v in music_meta.items() if v})
        meta["release_name"] = release_path.name
        meta["source_path"] = str(release_path)

    tmdb_key = cfg.get("metadata", {}).get("tmdb_api_key", "")
    if is_video_meta and tmdb_key:
        meta = tmdb_search(meta, tmdb_key, is_series=is_series)
        if meta.get("imdb_id"):
            meta = tmdb_find_by_imdb_id(meta, tmdb_key, is_series=is_series)

    paths = cfg["paths"]

    nfo_path, is_original = prepare_nfo(release_path, Path(paths["nfo_output"]), meta)

    if is_music:
        if is_original:
            # Eredeti NFO esetén csak a szükséges mezőket olvassuk ki az NFO-ból.
            # Tracklistet nem építünk, mert az NFO tartalmazza, és a description üres.
            if not meta.get("music_style"):
                meta["music_style"] = infer_music_style(release_path, meta)
        else:
            # Nem eredeti / NFO nélküli zenei release:
            # elsődleges forrás az audio tag, utána külső adatbázisok.
            meta = enrich_music_from_audio_tags(meta, release_path)

            meta = enrich_music_with_spotify(meta)

            discogs_token = cfg.get("discogs", {}).get("token", "") or os.getenv("DISCOGS_TOKEN", "")
            meta = enrich_music_metadata(meta, discogs_token)

            meta = musicbrainz_enrich_metadata(meta)

            if not meta.get("music_style"):
                meta["music_style"] = infer_music_style(release_path, meta)

            # Nem eredeti zenei release-nél a lokális fájlok tracklistje az elsődleges,
            # mert több CD-s kiadványoknál a Spotify gyakran csak egy lemezt/listát ad.
            print("Tracklist építése fájlokból/tag-ekből...")
            local_tracklist = build_tracklist_from_tags(release_path)
            if local_tracklist:
                meta["tracklist"] = local_tracklist


    meta = manual_metadata_prompt(meta, is_music=is_music)

    if is_music and not is_original and not best_original_proof_url(meta):
        url = input("Zenei adatbázis URL igazoláshoz [Discogs/MusicBrainz/Spotify, Enter = kihagy]: ").strip()
        if url:
            meta = apply_manual_music_url(meta, url)

    # Külső adatbázis-linkek / kézi meta után frissítsük az eredetiséget igazoló linket.
    meta["original_proof_url"] = best_original_proof_url(meta)

    if is_music and not is_original:
        normalized_name = normalize_music_display_name(meta)
        if normalized_name:
            print(f"Torrentnév normalizálva szabályzat szerint: {release_path.name} -> {normalized_name}")
            meta["torrent_name"] = normalized_name

    if is_music and not is_original:
        print("Zenei release: nincs eredeti NFO, generált zenei NFO készül.")
        nfo_path = build_music_generated_nfo(release_path, meta, Path(paths["nfo_output"]))
        print(f"Generált zenei NFO: {nfo_path}")

    techinfo = None
    screenshots: list[Path] = []

    if is_music and not is_original:
        for action in prepare_music_filelist_for_rules(category_value, release_path):
            print(f"Szabályzat szerinti fájllista-előkészítés: {action}")

    if is_music and not is_original:
        try:
            techinfo = build_music_techinfo(release_path, meta, Path(paths["techinfo_output"]))
            print(f"Generált zenei TechInfo: {techinfo}")
        except Exception as e:
            techinfo = None
            print(f"Zenei TechInfo generálás nem sikerült: {e}")
    elif media_file:
        if not is_original:
            try:
                techinfo = mediainfo_text(media_file, Path(paths["techinfo_output"]))
            except Exception as e:
                print(f"TechInfo generálás nem sikerült: {e}")

        if category_value in VIDEO_CATEGORIES:
            try:
                screenshots = generate_screenshots(media_file, Path(paths["screenshots_output"]))
            except Exception as e:
                print(f"Screenshot generálás nem sikerült: {e}")

    infobar_image = None

    if is_music:
        local_cover = find_local_cover(release_path)
        if local_cover:
            print(f"Infobar kép helyi borítóból: {local_cover}")
            infobar_image = make_infobar_from_local_image(
                local_cover,
                Path(paths["images_output"]),
                name=f"{release_path.stem}_infobar.jpg",
            )

        if not infobar_image:
            nfo_cover_url = cover_url_from_nfo(release_path)
            if nfo_cover_url:
                print("Infobar kép NFO-ban talált URL-ből.")
                infobar_image = download_infobar_image(
                    nfo_cover_url,
                    Path(paths["images_output"]),
                    name=f"{release_path.stem}_infobar.jpg",
                )

        if not infobar_image and meta.get("spotify_cover_url"):
            print("Infobar kép Spotify-ból.")
            infobar_image = download_infobar_image(
                meta.get("spotify_cover_url"),
                Path(paths["images_output"]),
                name=f"{release_path.stem}_infobar.jpg",
            )

        if not infobar_image and meta.get("discogs_cover_url"):
            print("Infobar kép Discogs-ból.")
            infobar_image = download_infobar_image(
                meta.get("discogs_cover_url"),
                Path(paths["images_output"]),
                name=f"{release_path.stem}_infobar.jpg",
            )

        if not infobar_image and meta.get("musicbrainz_cover_url"):
            print("Infobar kép MusicBrainz/Cover Art Archive-ból.")
            infobar_image = download_infobar_image(
                meta.get("musicbrainz_cover_url"),
                Path(paths["images_output"]),
                name=f"{release_path.stem}_infobar.jpg",
            )

        if not infobar_image:
            cover_url = musicbrainz_cover_url(meta)
            if cover_url:
                print("Infobar kép MusicBrainz/Cover Art Archive-ból.")
                infobar_image = download_infobar_image(
                    cover_url,
                    Path(paths["images_output"]),
                    name=f"{release_path.stem}_infobar.jpg",
                )

    if not infobar_image and meta.get("poster_url"):
        infobar_image = download_infobar_image(
            meta.get("poster_url"),
            Path(paths["images_output"]),
            name=f"{release_path.stem}_infobar.jpg",
        )

    torrent_file = create_torrent(release_path, Path(paths["torrent_output"]))

    prepared = {
        "release_path": str(release_path),
        "category_label": category_label,
        "category_value": category_value,
        "torrent_name": meta.get("torrent_name") or release_path.name,
        "is_original_release": is_original,
        "torrent_file": str(torrent_file),
        "nfo_file": str(nfo_path),
        "techinfo_file": str(techinfo) if techinfo else None,
        "screenshots": [str(p) for p in screenshots],
        "infobar_image": str(infobar_image) if infobar_image else None,
        "metadata": meta,
        "original_proof_url": best_original_proof_url(meta),
    }

    if is_music and not is_original:
        prepared["description"] = build_music_non_original_description(
            meta,
            torrent_name=release_path.name,
        )
    else:
        prepared["description"] = build_description(prepared)
    return prepared, cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="nCore universal uploader preparer")
    parser.add_argument("release", help="File or folder to prepare")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-browser", action="store_true", help="Only prepare files, do not upload")
    parser.add_argument("--submit", action="store_true", help="Submit HTTP upload to nCore")
    parser.add_argument("--validate", action="store_true", help="Validate prepared upload and exit")
    args = parser.parse_args()

    prepared, cfg = prepare(args)

    print("\nÖsszegzés:")
    print(f"Kategória: {prepared['category_label']} -> {prepared['category_value']}")
    print(f"Eredeti release: {'igen' if prepared['is_original_release'] else 'nem'}")
    print(f"Torrent: {prepared['torrent_file']}")
    print(f"NFO: {prepared['nfo_file']}")
    print(f"TechInfo: {prepared['techinfo_file']}")
    print(f"Képek: {prepared['screenshots']}")
    print(f"Infobar kép: {prepared['infobar_image']}")

    if args.validate:
        validate_prepared(prepared)
        return

    if not args.no_browser:
        resp = upload_http(
            prepared,
            cfg["ncore"]["upload_url"],
            cookie_file=cfg.get("auth", {}).get("cookies_file", "auth/ncore.txt"),
            submit=args.submit,
        )

        if args.submit and resp is not None:
            if not upload_response_successful(resp.text):
                print("Feltöltés nem volt sikeres vagy dupe/hibaoldal jött vissza, seedelést kihagyom.")
                return

            final_torrent = download_uploaded_torrent(
                resp.text,
                cookie_file=cfg.get("auth", {}).get("cookies_file", "auth/ncore.txt"),
            )
            if final_torrent:
                add_torrent_for_seeding(
                    final_torrent,
                    str(Path(prepared["release_path"]).parent),
                    category="ncore",
                )


if __name__ == "__main__":
    main()
