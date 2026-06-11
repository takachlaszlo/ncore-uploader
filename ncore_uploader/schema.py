from __future__ import annotations

NCORE_CATEGORIES = {
    "1": ("Film (HUN SD)", "xvid_hun"),
    "2": ("Film (ENG SD)", "xvid"),
    "3": ("Film (HUN DVD)", "dvd_hun"),
    "4": ("Film (ENG DVD)", "dvd"),
    "5": ("Film (HUN DVD9)", "dvd9_hun"),
    "6": ("Film (ENG DVD9)", "dvd9"),
    "7": ("Film (HUN HD)", "hd_hun"),
    "8": ("Film (ENG HD)", "hd"),
    "9": ("Sorozat (HUN SD)", "xvidser_hun"),
    "10": ("Sorozat (ENG SD)", "xvidser"),
    "11": ("Sorozat (HUN DVD)", "dvdser_hun"),
    "12": ("Sorozat (ENG DVD)", "dvdser"),
    "13": ("Sorozat (HUN HD)", "hdser_hun"),
    "14": ("Sorozat (ENG HD)", "hdser"),
    "15": ("MP3 (HUN)", "mp3_hun"),
    "16": ("MP3 (ENG)", "mp3"),
    "17": ("Lossless (HUN)", "lossless_hun"),
    "18": ("Lossless (ENG)", "lossless"),
    "19": ("Klip", "clip"),
    "20": ("Játék (ISO)", "game_iso"),
    "21": ("Játék (RIP)", "game_rip"),
    "22": ("Konzol", "console"),
}

VIDEO_CATEGORIES = {
    "xvid_hun", "xvid", "dvd_hun", "dvd", "dvd9_hun", "dvd9", "hd_hun", "hd",
    "xvidser_hun", "xvidser", "dvdser_hun", "dvdser", "hdser_hun", "hdser", "clip"
}
SERIES_CATEGORIES = {"xvidser_hun", "xvidser", "dvdser_hun", "dvdser", "hdser_hun", "hdser"}
MUSIC_CATEGORIES = {"mp3_hun", "mp3", "lossless_hun", "lossless", "clip"}
GAME_CATEGORIES = {"game_iso", "game_rip", "console"}

MUSIC_TAGS = [
    "60s", "70s", "80s", "90s", "acid", "alternative", "ambient", "blues", "breaks",
    "classical", "country", "dance", "death.metal", "disco", "drum.and.bass", "dub",
    "dubstep", "electronic", "emo", "euro.disco", "euro.house", "eurodance", "europop",
    "experimental", "folk", "funk", "garage", "goa.trance", "grunge", "hardcore",
    "hardcore.dance", "hardstyle", "hip.hop", "house", "indie.rock", "industrial",
    "italo.disco", "jazz", "latin", "live", "metal", "musical", "new.age", "ost",
    "pop", "pop.rock", "progressive.house", "progressive.rock", "progressive.trance",
    "psychedelic", "psytrance", "punk", "reggae", "rhythm.and.blues", "rock", "ska",
    "soul", "synth.pop", "techno", "trance", "trip.hop", "uk.garage", "world.music",
]

MUSIC_TAG_MAP = {
    "hip hop": "hip.hop", "hip-hop": "hip.hop", "r&b": "rhythm.and.blues",
    "rhythm and blues": "rhythm.and.blues", "drum and bass": "drum.and.bass",
    "dnb": "drum.and.bass", "synthpop": "synth.pop", "soundtrack": "ost",
    "score": "ost", "world": "world.music", "progressive rock": "progressive.rock",
    "progressive house": "progressive.house", "indie rock": "indie.rock",
}
