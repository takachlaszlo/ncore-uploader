# nCore universal uploader v1

Biztonságos v1: előkészít + kitölti az űrlapot, de nem küldi be automatikusan. Csak saját / engedélyezett tartalomhoz használd.

## Mit tud?

- kategória kézi kiválasztása menüből
- `.nfo` keresése a release mappában
  - ha van `.nfo`: `eredeti = igen`, ezt tölti fel
  - ha nincs `.nfo`: generál egy NFO-t, `eredeti = nem`
- `.torrent` generálás `mktorrent`-tel
- nem eredeti videónál `mediainfo` techinfo generálás
- nem eredeti videónál 3 screenshot generálás `ffmpeg`-gel
- audio/felirat összegzés `ffprobe` alapján
- Playwrighttal kitölti az nCore űrlapot
- nem nyomja meg a végleges submitot

## Telepítés Debian/Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg mediainfo mktorrent

cd ncore_universal_uploader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp config.example.yaml config.yaml
```

## Első futtatás

```bash
source venv/bin/activate
python uploader.py "/home/accofil/uploads/Release.Name.2025.1080p.WEB-DL.x264-GROUP"
```

Első alkalommal a Playwright külön böngészőprofilt nyit. Jelentkezz be nCore-ra kézzel. A profil mentődik a `browser_profile` mappába.

## Csak előkészítés böngésző nélkül

```bash
python uploader.py "/path/to/release" --no-browser
```

## Fontos

A script v1-ben direkt nem automatikus végleges feltöltő. Az űrlapot ellenőrizni kell, és csak kézzel küldd be.
