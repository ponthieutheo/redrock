#!/usr/bin/env python3
"""Affiche le lien d'appairage du chat RedRock (à ouvrir une fois sur chaque appareil).

Usage : python3 ops/pair.py [adresse du dashboard]   (par défaut : DASH_URL de config/chat.env, sinon http://127.0.0.1:8750)
Le code d'accès voyage dans le fragment (#cle=…) : le navigateur ne l'envoie jamais au serveur, l'app l'enregistre puis l'efface de l'adresse.
Lecture seule. Ensuite, les autres appareils s'appairent depuis l'app : Réglages > Appareils > Appairer (QR code).
"""
import os
import shutil
import subprocess
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env_value(path, name):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def main():
    env = os.path.join(ROOT, "config", "chat.env")
    key = env_value(env, "CHAT_KEY")
    if not key:
        sys.exit("CHAT_KEY introuvable dans config/chat.env : le chat est désactivé.")
    base = (sys.argv[1] if len(sys.argv) > 1 else env_value(env, "DASH_URL") or "http://127.0.0.1:8750").rstrip("/")
    link = f"{base}/#cle={quote(key, safe='')}"
    print("Lien d'appairage (secret, ne le partage pas) :\n\n  " + link + "\n")
    if shutil.which("qrencode"):
        subprocess.run(["qrencode", "-t", "ansiutf8", link])
    else:
        print("(installe « qrencode » pour l'afficher aussi en QR code dans le terminal)")


if __name__ == "__main__":
    main()
