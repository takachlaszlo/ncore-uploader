from __future__ import annotations

from pathlib import Path
from ncore_uploader.policy import validate_policy


VIDEO_CATEGORIES = {"xvid_hun", "xvid", "dvd_hun", "dvd", "dvd9_hun", "dvd9", "hd_hun", "hd",
                    "xvidser_hun", "xvidser", "dvdser_hun", "dvdser", "hdser_hun", "hdser"}
MUSIC_CATEGORIES = {"mp3_hun", "mp3", "lossless_hun", "lossless", "clip"}


def ok(label: str):
    print(f"✓ {label}")


def fail(label: str):
    print(f"✗ {label}")


def validate_prepared(prepared: dict) -> bool:
    good = True
    meta = prepared.get("metadata", {})
    category = prepared.get("category_value")

    checks = [
        ("torrent", prepared.get("torrent_file")),
    ]

    for label, path in checks:
        if path and Path(path).exists():
            ok(label)
        else:
            fail(label)
            good = False

    is_va = bool(meta.get("is_va"))
    if prepared.get("infobar_image") and Path(prepared["infobar_image"]).exists():
        ok("infobar kép")
    elif prepared.get("is_original_release"):
        print("- infobar kép: eredeti release-nél nem kötelező")
    elif is_va:
        print("- infobar kép: VA release-nél nem kötelező")
    else:
        fail("infobar kép")
        good = False

    if prepared.get("is_original_release"):
        if prepared.get("nfo_file") and Path(prepared["nfo_file"]).exists():
            ok("eredeti/generált NFO")
        else:
            fail("NFO")
            good = False

    if category in VIDEO_CATEGORIES:
        if meta.get("imdb_id"):
            ok("IMDb")
        else:
            fail("IMDb")
            good = False

        if meta.get("audio_tracks"):
            ok("hangsáv")
        else:
            fail("hangsáv")
            good = False

        shots = prepared.get("screenshots", [])
        if len(shots) >= 3 and all(Path(p).exists() for p in shots[:3]):
            ok("3 screenshot")
        else:
            fail("3 screenshot")
            good = False

    if category in MUSIC_CATEGORIES:
        if meta.get("artist"):
            ok("előadó")
        else:
            fail("előadó")
            good = False

        if meta.get("album"):
            ok("album")
        else:
            fail("album")
            good = False

        if meta.get("album_year"):
            ok("év")
        else:
            fail("év")
            good = False

        if meta.get("music_style"):
            ok("stílus")
        else:
            fail("stílus")
            good = False

        if prepared.get("is_original_release"):
            print("- tracklist: eredeti NFO release, nem ellenőrzöm")
        elif meta.get("tracklist"):
            ok("tracklist")
        else:
            fail("tracklist")
            good = False

    policy_errors = validate_policy(prepared)
    if policy_errors:
        for err in policy_errors:
            fail(err)
        good = False
    else:
        ok("szabályzat: alap ellenőrzések")

    print("")
    print("READY TO UPLOAD" if good else "NOT READY")
    return good
