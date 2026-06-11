cd ~/ncore_universal_uploader

cat > README.md <<'EOF'
# nCore Uploader

Ez a projekt egy saját használatra készült nCore feltöltő / előkészítő eszközkészlet.

A célja:

- release mappából vagy fájlból `.torrent` készítése;
- NFO, TechInfo, screenshot, infobar kép előkészítése;
- nCore feltöltési űrlap HTTP alapú kitöltése;
- sikeres feltöltés után az nCore-os torrent letöltése;
- a torrent visszaadása qBittorrentbe seedelésre;
- zenei release-ek tömeges feltöltése listából;
- autobrr/qBittorrent `music` taggel érkező zenei scene release-ek automatikus feltöltése.

A projekt jelenleg aktív fejlesztés alatt áll. Elsősorban saját workflow-ra készült.

---

## Tartalom

A repository fő fájljai:

- `uploader.py`  
  A fő feltöltő script. Egy release mappát vagy fájlt dolgoz fel.

- `batch_upload.py`  
  Több zenei release feltöltése egy listafájlból.

- `generate_music_batch_list.py`  
  A zenei letöltési mappából listát készít a batch feltöltőhöz.

- `qbit_finished_music_autoupload.py`  
  qBittorrent “Run external program on torrent finished” hook. Automatikusan próbálja feltölteni az elkészült zenei scene release-eket.

- `ncore_login.py`  
  nCore cookie mentése `auth/ncore.txt` fájlba.

- `install.sh`  
  Telepítő script. Létrehozza a venv-et, telepíti a Python csomagokat, majd bekéri a szükséges API kulcsokat és útvonalakat.

- `config.example.yaml`  
  Minta konfiguráció. Az install ebből készít `config.yaml` fájlt.

- `.env.example`  
  Minta környezeti változók. Az install ebből / bekért adatokból készít `.env` fájlt.

- `requirements.txt`  
  Python függőségek listája.

- `ncore_uploader/`  
  A belső modulok mappája.

Fontosabb modulok:

- `ncore_uploader/music.py` — zenei release parser, tracklist, generált NFO, MusicBrainz/Discogs kiegészítés.
- `ncore_uploader/spotify.py` — Spotify keresés, albumadatok, borító, tracklist.
- `ncore_uploader/discogs.py` — Discogs keresés.
- `ncore_uploader/tmdb.py` — TMDb keresés filmekhez/sorozatokhoz.
- `ncore_uploader/http_upload.py` — HTTP alapú nCore feltöltés, válasz HTML mentése, hibák kinyerése.
- `ncore_uploader/validate.py` — feltöltés előtti validáció.
- `ncore_uploader/policy.py` — szabályzati ellenőrzések és névnormalizálások.
- `ncore_uploader/qbit.py` — qBittorrent Web API kapcsolat.

---

## Amit NEM szabad GitHubra tenni

Ezek érzékeny vagy gépfüggő fájlok, a `.gitignore` kihagyja őket:

- `.env`
- `config.yaml`
- `auth/`
- `browser_profile/`
- `work/`

Mit tartalmaznak?

- `.env`  
  API kulcsok, jelszavak, lokális útvonalak.

- `config.yaml`  
  Aktív konfiguráció, például tracker announce URL.

- `auth/`  
  nCore cookie.

- `browser_profile/`  
  Playwright/Chromium profil.

- `work/`  
  Generált torrentek, NFO-k, TechInfo fájlok, screenshotok, upload válasz HTML-ek, logok.

---

## Rendszerkövetelmények

Debian/Ubuntu rendszeren ajánlott.

Szükséges rendszerprogramok:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg mediainfo mktorrent git

Mit mire használ?

python3 / python3-venv: Python futtatókörnyezet.
ffmpeg / ffprobe: screenshot generálás, hang/felirat információk.
mediainfo: TechInfo készítés.
mktorrent: torrent fájl létrehozása.
git: GitHubról klónozás és verziókezelés.
Telepítés új gépen
1. Repository klónozása

SSH-val:

git clone git@github.com:takachlaszlo/ncore-uploader.git
cd ncore-uploader

HTTPS-sel:

git clone https://github.com/takachlaszlo/ncore-uploader.git
cd ncore-uploader
2. Telepítő futtatása
chmod +x install.sh
./install.sh

A telepítő:

létrehozza a venv virtuális környezetet;
telepíti a requirements.txt csomagjait;
bekéri az API kulcsokat;
bekéri a qBittorrent adatokat;
bekéri a fontos lokális útvonalakat;
létrehozza a .env fájlt;
létrehozza a config.yaml fájlt;
létrehozza a szükséges munkamappákat.
3. Virtuális környezet aktiválása
source venv/bin/activate

Ha minden rendben, a prompt elején ilyesmit látsz:

(venv)
Az install.sh által bekért adatok
TMDb API key

Film/sorozat metaadatokhoz kell.

.env mező:

TMDB_API_KEY=

config.yaml mező:

metadata:
  tmdb_api_key: ""
Spotify Client ID és Client Secret

Zenei metaadatokhoz, borítóhoz, tracklisthez.

SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
Discogs token

Zenei eredetiséget igazoló linkhez és stílusokhoz.

DISCOGS_TOKEN=
qBittorrent URL

qBittorrent Web UI címe.

Példa:

QB_URL=http://127.0.0.1:8080
qBittorrent username / password

qBittorrent Web UI login.

QB_USER=
QB_PASS=
nCore upload URL

Általában:

NCORE_UPLOAD_URL=https://ncore.pro/upload.php
nCore announce / tracker URL

Ez kerül a generált .torrent fájlba.

NCORE_ANNOUNCE_URL=

Fontos: ezt pontosan kell megadni, különben a generált torrent nem lesz megfelelő.

Projekt útvonala

A projekt abszolút útvonala.

Példa:

NCORE_UPLOAD_BASE=/path/to/ncore-uploader
Zenei watch mappa

Az a mappa, ahol a qBittorrent/autobrr által letöltött zenei release-ek vannak.

MUSIC_WATCH_DIR=/path/to/qbittorrent/music
qBittorrent alap mentési mappa

A qBittorrent fő letöltési mappája.

QBIT_SAVE_ROOT=/path/to/qbittorrent
Python bináris

A projekt venv Pythonja.

PYTHON_BIN=/path/to/ncore-uploader/venv/bin/python
Fő használat: uploader.py

Alap forma:

python uploader.py "/path/to/release"

A script először kategóriát kér.

Példa kategóriák:

16 - MP3 (ENG)
18 - Lossless (ENG)
14 - Sorozat (ENG HD)
8  - Film (ENG HD)
Mit csinál az uploader?

Release típusától függően:

megkeresi az .nfo fájlt;
eldönti, hogy eredeti release-e;
ha nincs NFO, zenei NFO-t generálhat;
zenei release-nél Spotify / Discogs / MusicBrainz alapján metaadatot keres;
film/sorozatnál TMDb alapján metaadatot keres;
MediaInfo TechInfo-t készít;
screenshotokat készít videóhoz;
infobar képet készít;
.torrent fájlt generál;
validálja az előkészített anyagot;
feltöltéskor HTTP POST-tal elküldi az nCore upload formot;
sikeres feltöltés után letölti az nCore által generált torrentet;
visszaadja qBittorrentbe seedelésre.
uploader.py kapcsolók
--validate

Csak ellenőriz, nem tölt fel.

python uploader.py --validate --no-browser "/path/to/release"

Mire jó?

Megnézni, hogy a release feltölthető-e.
Ha READY TO UPLOAD, akkor átment a validáción.
Ha NOT READY, akkor a kimenetben látod, mi hiányzik.
--no-browser

Nem indít böngészőt és nem próbál feltölteni.

python uploader.py --no-browser "/path/to/release"
--submit

Éles feltöltés.

python uploader.py --submit "/path/to/release"

Mit csinál?

kitölti és beküldi az nCore upload formot;
menti a válasz HTML-t;
ha sikeres, kinyeri a torrent ID-t;
letölti az nCore által generált torrentet;
hozzáadja qBittorrenthez seedelésre.

Fontos: --submit nélkül nem történik tényleges feltöltés.

--config

Másik config fájl használata.

python uploader.py --config config.yaml "/path/to/release"

Alapértelmezett:

config.yaml
nCore login cookie készítése

A HTTP feltöltéshez nCore cookie kell.

Futtatás:

python ncore_login.py

Bekéri:

nCore felhasználónév;
nCore jelszó;
2FA kód, ha van.

Siker esetén létrejön:

auth/ncore.txt
Zenei batch feltöltés

A batch workflow két részből áll:

lista generálása;
lista feltöltése.
Zenei release lista generálása

Alap:

python generate_music_batch_list.py

Ha kézzel akarsz root mappát adni:

python generate_music_batch_list.py --root "/path/to/music"

Kimenet:

work/music_batch_list.txt
Batch feltöltés listából

Csak validáció / előkészítés:

./batch_upload.py work/music_batch_list.txt

Éles feltöltés:

./batch_upload.py work/music_batch_list.txt --submit

Fontos:

--submit nélkül nem tölt fel.

Log:

work/batch_upload.log

Mentett nCore HTML válaszok:

work/upload_responses/
qBittorrent automatikus zenei feltöltés

Ez a legfontosabb automatizált rész.

A script:

qbit_finished_music_autoupload.py

qBittorrentből akkor fut le, amikor egy torrent elkészült.

qBit autoupload biztonsági kapuk

A script csak akkor megy tovább, ha minden igaz:

A torrent qBittorrent tagjei között van:
music
Tartalmaz zenei fájlt:
.mp3
.flac
.m4a
.ape
.wav
.dts
.mka
Nem tartalmaz videófájlt:
.mkv
.mp4
.avi
.mov
.wmv
.ts
.m2ts
.vob
.iso
Tartalmaz .nfo fájlt.
Scene zenei release-nek tűnik a neve alapján.
Még nincs feldolgozva a state fájl szerint.

State fájl:

work/qbit_auto_upload_state.json

Log fájl:

work/qbit_auto_upload.log

Ha valami elhasal, a script nem teszi state-be, tehát később újrapróbálható.

qBittorrent beállítás: Run external program

qBittorrent Web UI-ban keresd ezt:

Run external program on torrent finished

Ide ezt kell beírni.

Általános forma:

/path/to/project/venv/bin/python /path/to/project/qbit_finished_music_autoupload.py "%F" "%N" "%R" "%L"

Példa:

/home/USER/ncore-uploader/venv/bin/python /home/USER/ncore-uploader/qbit_finished_music_autoupload.py "%F" "%N" "%R" "%L"

Az argumentumok jelentése:

%F — a torrent tartalmának útvonala.
%N — torrent neve.
%R — save path / mentési gyökér.
%L — qBittorrent tag-ek / label-ek.

Nagyon fontos: a %L kell, mert ebből látja a script, hogy van-e music tag.

Ha nincs %L, akkor a script ezt írja:

SKIP: nincs music qBit tag, nem zenei autoupload
autobrr beállítás

Az autobrr-nek a zenei torrenteket music taggel kell átadnia qBittorrentbe.

Elvárt qBittorrent tag:

music

Ez védi ki, hogy film/sorozat/videós mappa véletlenül zenei kategóriába menjen.

qBit autoupload kézi teszt

Music tag nélkül skipelnie kell:

./qbit_finished_music_autoupload.py \
"/path/to/music/release" \
"Release.Name-WEB-2026-GROUP" \
"/path/to/qbit/root"

Elvárt:

SKIP: nincs music qBit tag, nem zenei autoupload

Music taggel tovább kell mennie:

./qbit_finished_music_autoupload.py \
"/path/to/music/release" \
"Release.Name-WEB-2026-GROUP" \
"/path/to/qbit/root" \
"music"

Videós mappára skipelnie kell:

SKIP: videófájlt tartalmaz, nem zenei autoupload

NFO nélküli mappára skipelnie kell:

SKIP: nincs .nfo, nem automata scene zenei release
Munkamappák

A work/ mappa generált fájlokat tartalmaz.

work/torrents/ — generált .torrent fájlok.
work/nfo/ — generált NFO-k.
work/techinfo/ — MediaInfo TechInfo fájlok.
work/images/ — infobar képek.
work/screenshots/ — videós screenshotok.
work/downloaded_torrents/ — nCore-ról letöltött végleges torrentek.
work/upload_responses/ — nCore upload válasz HTML-ek.
work/excluded_from_ncore_upload/ — kizárt fájlok.
work/batch_upload.log — batch log.
work/qbit_auto_upload.log — qBit autoupload log.
Gyakori hibák
ModuleNotFoundError: No module named PIL

Nem a venv Python fut.

Megoldás:

source venv/bin/activate
pip install -r requirements.txt

qBitben pedig ne /usr/bin/python3 legyen, hanem:

/path/to/project/venv/bin/python /path/to/project/qbit_finished_music_autoupload.py "%F" "%N" "%R" "%L"
SKIP: nincs music qBit tag

A qBittorrent nem adta át a music taget, vagy a parancsból hiányzik %L.

SKIP: videófájlt tartalmaz

A mappa nem tiszta zenei release, vagy videófájl van benne. Ez szándékos védelem.

SKIP: nincs .nfo

Az autoupload csak eredeti scene zenei release-eket próbál automatikusan feltölteni.

NOT READY

A validáció nem engedte a feltöltést.

Futtasd kézzel:

python uploader.py --validate --no-browser "/path/to/release"
A feltöltött torrent már létezik

Dupe. Az nCore már tartalmazza.

A válasz HTML mentődik:

work/upload_responses/
Git használat

Változtatás után:

git status
git add .
git commit -m "Leíró commit üzenet"
git push

Nem szabad commitba kerülnie:

.env
config.yaml
auth/
browser_profile/
work/

Titokellenőrzés:

grep -R "SPOTIFY_CLIENT_SECRET\|DISCOGS_TOKEN\|QB_PASS" . \
  --exclude-dir=.git \
  --exclude=.env

Normális találatok:

.env.example
install.sh
README.md

Valódi token/jelszó ne legyen commitolt fájlban.

Frissítés GitHubról
cd /path/to/ncore-uploader
git pull
source venv/bin/activate
pip install -r requirements.txt

Ha az install változott, újra lehet futtatni:

./install.sh

Figyelem: ez felülírhatja a .env és config.yaml fájlokat, ezért előtte mentsd őket, ha kell.

Rövid napi használati összefoglaló

Egy release kézi validálása:

python uploader.py --validate --no-browser "/path/to/release"

Egy release éles feltöltése:

python uploader.py --submit "/path/to/release"

Zenei lista generálása:

python generate_music_batch_list.py

Zenei lista éles feltöltése:

./batch_upload.py work/music_batch_list.txt --submit

qBit autoupload log nézése:

tail -100 work/qbit_auto_upload.log

Batch log nézése:

tail -100 work/batch_upload.log
Fontos korlátozások
Az autoupload jelenleg csak zenei scene release-ekre való.
Az autoupload csak music qBit taggel indul.
Videófájlt tartalmazó mappát nem tölt fel zeneként.
NFO nélküli release automatikusan nem megy.
--submit nélkül nincs éles feltöltés.
A generált fájlok a work/ mappába kerülnek.
Az .env, config.yaml, auth/, work/ nem GitHubra való.
EOF

Utána:

```bash
git add README.md
git commit -m "Expand README with detailed usage guide"
git push
