from __future__ import annotations
from pathlib import Path
import json
import subprocess

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".mov", ".m2ts", ".ts"}
AUDIO_EXTS = {".flac", ".mp3", ".m4a", ".wav", ".aac"}


def first_media_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS | AUDIO_EXTS]
    if not files:
        return None
    return sorted(files, key=lambda p: p.stat().st_size, reverse=True)[0]


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def mediainfo_text(media_file: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{media_file.name}.mediainfo.txt"
    out.write_text(run(["mediainfo", str(media_file)]), encoding="utf-8", errors="replace")
    return out


def ffprobe_json(media_file: Path) -> dict:
    out = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(media_file)])
    return json.loads(out)


def duration_seconds(media_file: Path) -> float:
    data = ffprobe_json(media_file)
    dur = data.get("format", {}).get("duration")
    return float(dur) if dur else 0.0


LANG_MAP = {
    "eng": "Angol",
    "hun": "Magyar",
    "ger": "Német",
    "deu": "Német",
    "fre": "Francia",
    "fra": "Francia",
    "spa": "Spanyol",
    "ita": "Olasz",
    "jpn": "Japán",
    "kor": "Koreai",
    "chi": "Kínai",
    "zho": "Kínai",
    "rus": "Orosz",
    "und": "Ismeretlen",
}


def normalize_lang(lang: str | None) -> str:
    if not lang:
        return "Ismeretlen"
    return LANG_MAP.get(lang.lower().strip(), lang.upper())


def normalize_channels(channels) -> str:
    try:
        ch = int(channels)
    except Exception:
        return ""
    return {
        1: "1.0",
        2: "2.0",
        3: "2.1",
        4: "4.0",
        5: "5.0",
        6: "5.1",
        7: "6.1",
        8: "7.1",
    }.get(ch, f"{ch} ch")


def unique_keep_order(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_audio_subtitle_summary(media_file: Path) -> tuple[str, str]:
    data = ffprobe_json(media_file)
    audio, subs = [], []

    for stream in data.get("streams", []):
        tags = stream.get("tags", {}) or {}
        lang = normalize_lang(tags.get("language"))
        codec_type = stream.get("codec_type")

        if codec_type == "audio":
            ch = normalize_channels(stream.get("channels"))
            audio.append(" ".join(x for x in [lang, ch] if x))

        elif codec_type == "subtitle":
            subs.append(lang)

    return ", ".join(unique_keep_order(audio)), ", ".join(unique_keep_order(subs))


def generate_screenshots(media_file: Path, output_dir: Path, count: int = 3) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dur = duration_seconds(media_file)
    if dur <= 0:
        positions = [300, 900, 1800]
    else:
        positions = [dur * 0.2, dur * 0.5, dur * 0.8]
    outs = []
    for i, pos in enumerate(positions[:count], start=1):
        out = output_dir / f"{media_file.stem}.sample{i}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(int(pos)), "-i", str(media_file),
            "-frames:v", "1", "-q:v", "2", str(out)
        ], check=True)
        outs.append(out)
    return outs
