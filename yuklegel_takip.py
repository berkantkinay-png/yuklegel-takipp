#!/usr/bin/env python3
"""YükleGel ilan takipçisi (kişisel kullanım)"""
import json
import os
import re
import sys
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

URL = "https://yuklegel.com/"
KONTROL_ARALIGI_SN = 300


def _liste(ad, varsayilan):
    d = os.environ.get(ad)
    if d is None:
        return varsayilan
    return [k.strip() for k in d.split(",") if k.strip()]


ARANAN = _liste("ARANAN", ["istanbul", "gebze", "frigo"])
HARIC = _liste("HARIC", ["iran", "kazakistan", "bakü", "irak"])

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DURUM_DOSYASI = "gorulen_ilanlar.json"


def sadelestir(metin: str) -> str:
    metin = metin.replace("İ", "i").replace("I", "ı")
    metin = unicodedata.normalize("NFKD", metin.lower())
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    return metin.replace("ı", "i")


ARANAN_N = [sadelestir(k) for k in ARANAN]
HARIC_N = [sadelestir(k) for k in HARIC]
ID_RE = re.compile(r"id(?:=|%3[Dd])([0-9a-fA-F]{24})")


def sayfayi_cek() -> str:
    r = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=30,
    )
    r.raise_for_status()
    return r.text


def ilanlari_ayikla(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    ilanlar = {}
    for a in soup.find_all("a", href=True):
        m = ID_RE.search(a["href"])
        if not m or "movetheposttothetop" not in a["href"]:
            continue
        ilan_id = m.group(1)
        kutu = a
        for _ in range(6):
            ust = kutu.parent
            if ust is None:
                break
            if len(ust.find_all("a", href=ID_RE)) > 1:
                break
            kutu = ust
        metin = kutu.get_text("\n", strip=True)
        metin = re.sub(r"\n?(Paylas|Paylaş|Arkadaşına Gönder)\n?", "\n", metin).strip()
        if metin:
            ilanlar[ilan_id] = metin
    return ilanlar


def uygun_mu(metin: str) -> bool:
    n = sadelestir(metin)
    if any(h in n for h in HARIC_N):
        return False
    if not ARANAN_N:
        return True
    return any(k in n for k in ARANAN_N)


def bildir(ilan_id: str, metin: str):
    link = f"https://yuklegel.com/home/movetheposttothetop?id={ilan_id}"
    mesaj = f"🚛 Yeni ilan\n\n{metin[:900]}\n\n{link}"
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": mesaj},
                timeout=20,
            )
        except Exception as e:
            print("Telegram hatası:", e)
    print("-" * 40)
    print(mesaj)


def durum_yukle() -> set:
    if os.path.exists(DURUM_DOSYASI):
        try:
            with open(DURUM_DOSYASI, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def durum_kaydet(gorulen: set):
    with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(list(gorulen)[-5000:], f)


def tur(gorulen: set, ilk_calisma: bool):
    ilanlar = ilanlari_ayikla(sayfayi_cek())
    yeni = {i: t for i, t in ilanlar.items() if i not in gorulen}
    print(f"{len(ilanlar)} ilan okundu, {len(yeni)} yeni.")
    if len(ilanlar) == 0:
        print("UYARI: Hic ilan ayiklanamadi.")
    for ilan_id, metin in yeni.items():
        gorulen.add(ilan_id)
        if not ilk_calisma and uygun_mu(metin):
            bildir(ilan_id, metin)
    durum_kaydet(gorulen)


def main():
    if "--debug" in sys.argv:
        with open("sayfa.html", "w", encoding="utf-8") as f:
            f.write(sayfayi_cek())
        print("sayfa.html kaydedildi.")
        return

    if "--test" in sys.argv:
        for i, t in ilanlari_ayikla(sayfayi_cek()).items():
            print(("✅ " if uygun_mu(t) else "❌ ") + t[:120].replace("\n", " | "))
        return

    gorulen = durum_yukle()
    ilk = len(gorulen) == 0

    if "--bir-kez" in sys.argv:
        tur(gorulen, ilk)
        return

    print("Takip basladi. Durdurmak icin Ctrl+C.")
    while True:
        try:
            tur(gorulen, ilk)
            ilk = False
        except Exception as e:
            print("Hata:", e)
        time.sleep(KONTROL_ARALIGI_SN)


if __name__ == "__main__":
    main()
