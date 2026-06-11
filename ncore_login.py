from __future__ import annotations

from http.cookiejar import MozillaCookieJar
from pathlib import Path
import getpass
import requests


COOKIE_FILE = Path("auth/ncore.txt")
LOGIN_URL = "https://ncore.pro/login.php?2fa"
UPLOAD_URL = "https://ncore.pro/upload.php"


def main():
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)

    username = input("nCore felhasználónév: ").strip()
    password = getpass.getpass("nCore jelszó: ")
    twofa = input("2FA kód, ha van [Enter ha nincs]: ").strip()

    jar = MozillaCookieJar(str(COOKIE_FILE))
    session = requests.Session()
    session.cookies = jar
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://ncore.pro/login.php",
    })

    data = {
        "submitted": "1",
        "nev": username,
        "pass": password,
        "ne_leptessen_ki": "1",
    }

    if twofa:
        data["2factor"] = twofa

    r = session.post(LOGIN_URL, data=data, allow_redirects=True, timeout=30)

    check = session.get(UPLOAD_URL, allow_redirects=True, timeout=30)

    print("Login utáni URL:", check.url)
    print("Upload form:", 'id="feltoltes"' in check.text)

    if 'id="feltoltes"' not in check.text:
        print("Nem sikerült belépni. Lehet CAPTCHA, hibás mezőnév vagy eltérő login-flow.")
        print("Válasz hossza:", len(check.text))
        return

    jar.save(ignore_discard=True, ignore_expires=True)
    print(f"Cookie mentve: {COOKIE_FILE}")


if __name__ == "__main__":
    main()
