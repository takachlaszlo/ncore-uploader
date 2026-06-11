#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


BASE = Path(__file__).resolve().parent
LOG = BASE / "work" / "batch_upload.log"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line)
    LOG.open("a", encoding="utf-8").write(line + "\n")


def infer_category_number(release: Path) -> str | None:
    files = [release] if release.is_file() else [p for p in release.rglob("*") if p.is_file()]
    exts = {p.suffix.lower() for p in files}

    if ".flac" in exts:
        return "18"  # Lossless ENG
    if ".mp3" in exts:
        return "16"  # MP3 ENG

    return None


def read_paths(list_file: Path) -> list[Path]:
    paths = []
    for line in list_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        paths.append(Path(line).expanduser())
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("list_file", help="Text file with one release path per line")
    ap.add_argument("--submit", action="store_true")
    args = ap.parse_args()

    list_file = Path(args.list_file).expanduser()
    if not list_file.exists():
        log(f"Lista nem létezik: {list_file}")
        return 2

    paths = read_paths(list_file)
    if not paths:
        log("Üres lista.")
        return 0

    ok = 0
    fail = 0

    for i, release in enumerate(paths, start=1):
        log(f"[{i}/{len(paths)}] Kezdem: {release}")

        if not release.exists():
            log(f"SKIP: nem létezik: {release}")
            fail += 1
            continue

        category = infer_category_number(release)
        if not category:
            log(f"SKIP: nem MP3/FLAC release: {release}")
            fail += 1
            continue

        # A jelenlegi uploader interaktív kategóriaválasztást vár.
        # Ezt stdin-ből adjuk át: kategória szám + Enterek a metaadatokra + Enter a feltöltés indításra.
        stdin_text = category + "\n\n\n\n\n\n"

        # Először validálunk. Ha nincs READY TO UPLOAD, nem submitolunk.
        validate_cmd = [
            sys.executable,
            str(BASE / "uploader.py"),
            "--validate",
            "--no-browser",
            str(release),
        ]

        validate_proc = subprocess.run(
            validate_cmd,
            cwd=str(BASE),
            input=stdin_text,
            text=True,
            capture_output=True,
        )

        LOG.open("a", encoding="utf-8").write("\n--- VALIDATE STDOUT ---\n" + validate_proc.stdout)
        LOG.open("a", encoding="utf-8").write("\n--- VALIDATE STDERR ---\n" + validate_proc.stderr)

        if validate_proc.returncode != 0 or "READY TO UPLOAD" not in validate_proc.stdout:
            log(f"SKIP: validáció sikertelen / nem READY: {release}")
            fail += 1
            continue

        cmd = [
            sys.executable,
            str(BASE / "uploader.py"),
        ]

        if args.submit:
            cmd.append("--submit")

        cmd.append(str(release))

        proc = subprocess.run(
            cmd,
            cwd=str(BASE),
            input=stdin_text,
            text=True,
            capture_output=True,
        )

        LOG.open("a", encoding="utf-8").write("\n--- STDOUT ---\n" + proc.stdout)
        LOG.open("a", encoding="utf-8").write("\n--- STDERR ---\n" + proc.stderr)

        if proc.returncode == 0 and "Feltöltés nem volt sikeres" not in proc.stdout:
            log(f"OK: {release}")
            ok += 1
        else:
            log(f"HIBA/SKIP: {release} exit={proc.returncode}")
            fail += 1

    log(f"Kész. OK={ok}, HIBA/SKIP={fail}")

    errlog = BASE / "work" / "upload_errors.log"
    if errlog.exists():
        log("")
        log("Feltöltési hibák összesítése:")
        print("")
        print("===== FELTÖLTÉSI HIBÁK ÖSSZESÍTÉSE =====")
        print(errlog.read_text(encoding="utf-8", errors="ignore")[-8000:])

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
