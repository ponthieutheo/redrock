"""Test hors ligne des bibliothèques embarquées (dash/vendor/) : servies par le dashboard, intactes, aucun CDN dans la page,
aucun chemin hors de la liste (« .. », encodages, fichiers non listés).
Lancer : python -I -X utf8 dash/test_vendor.py"""
import base64, gzip, hashlib, http.client, json, os, re, shutil, sys, tempfile, threading
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL="http://127.0.0.1:9")
sys.path.insert(0, HERE)
import dash

dash.DATA = tempfile.mkdtemp()
dp = ThreadingHTTPServer(("127.0.0.1", 0), dash.H)
threading.Thread(target=dp.serve_forever, daemon=True).start()


def req(path, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", dp.server_port, timeout=20)
    c.request("GET", path, headers=headers or {})
    r = c.getresponse()
    raw = r.read()
    h = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, h, raw


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True
ok.bad = False

V = os.path.join(HERE, "vendor")
read = lambda *p: open(os.path.join(HERE, *p), encoding="utf-8").read()
sri = lambda b, algo="sha384": f"{algo}-" + base64.b64encode(hashlib.new(algo, b).digest()).decode()

# --- empreintes : les fichiers sont ceux des paquets officiels (three 0.170.0 et polices @fontsource 5.3.0 : npm, tarball
#     vérifié contre l'empreinte du registre ; qrcode-generator 1.4.4 : cdnjs, vérifié contre le SRI de la page)
PINS = {
    "three/three.module.js": "sha384-GY5FqjttLCFRt/McQbyaVdCk2O1IQtOeX8Py6NfD89BIAsIyJFRl4UgSXrk2vXAk",
    "qrcode-generator/qrcode.min.js": "sha384-mZT2gIty7ZDdOGkxfP6joZcYdMW1Jvj9dRlfpTmaJAKKXTqzygtB22k7FLe+KZC1",
    "fonts/barlow-latin-400-normal.woff2": "sha384-koj/cMvDyHH4cN0XIhbyrDJdKvo7q2fkmvKOJA8bBgvuhhrfZcKxq4f1ybJwXjcT",
    "fonts/barlow-latin-500-normal.woff2": "sha384-x3avrN/alX1T1m0c3GXp7Fe9pCQPYocKPDkXOka0DOE227qlmrXAgUjf4OEAZPDt",
    "fonts/barlow-latin-600-normal.woff2": "sha384-tbuCC3XUJ7SyW+erhTeUuQPV/HSE0gg4arKSId7Tqa0oNDT15sUn1NfhnbY1Z174",
    "fonts/barlow-latin-ext-400-normal.woff2": "sha384-8tFklSC4RbheMz02DitMkZ0NaSBAJ2XeNm1ynOHBEP24G1IVS6VuCSCV6IebXkhD",
    "fonts/barlow-latin-ext-500-normal.woff2": "sha384-0tNQUEerOUZ2hVDCchPUW4VeC49Vh1TgCrYEAvxNyhfgmXpW/JpeXiBTQCkcnWKP",
    "fonts/barlow-latin-ext-600-normal.woff2": "sha384-A1zpHKH85huP4ui9XKx+hLmsAwiCKjpaUJAALVFKyTAig4DVSgmzgQ9mdm8+W3ok",
    "fonts/chakra-petch-latin-500-normal.woff2": "sha384-6CGs5k+fjBY9aihr8SOKTx8eP6uXr4qq4pp+HXbX20N3zfo68BQY8yPeNldz1SdC",
    "fonts/chakra-petch-latin-600-normal.woff2": "sha384-IBKIv5S8STpK2G81wNyEzGE5qgmeN15FAiq/lIINamVEi8l1Q5S2ga7VdRJY4RZN",
    "fonts/chakra-petch-latin-700-normal.woff2": "sha384-CQ3zi3/kD0WD6phQ8hHObPsXxw7lNIqsfGn1v7xO8SfG+VgRkFJOF/WUItZv4c4R",
    "fonts/chakra-petch-latin-ext-500-normal.woff2": "sha384-h1XD3vW5xVI9SU0Dq0pGYlJvW5nswZyHEo8wT8FWgude6JhUqcc780Eu++y6YwcL",
    "fonts/chakra-petch-latin-ext-600-normal.woff2": "sha384-H0cFexjjaSxI6la0+7+Qf4zkBmSx80LhUPMyXbo36fSdm80YxIlEnlklRG5Z+DMF",
    "fonts/chakra-petch-latin-ext-700-normal.woff2": "sha384-0WX8V5M024r5HBNAGN9NqPBQvZlkGcVf8cFPzcpUSEPa3dhwQ0mzBmEVxczmKz07",
}
bad = [p for p, h in PINS.items() if sri(open(os.path.join(V, p), "rb").read()) != h]
ok(f"{len(PINS)} fichiers embarqués intacts (empreintes)", not bad)
for p in bad:
    print("     modifié :", p)
for d in ("three", "qrcode-generator"):
    ok(f"licence de {d} présente (MIT)", "Permission is hereby granted" in read("vendor", d, "LICENSE"))
for f in ("LICENSE-ChakraPetch.txt", "LICENSE-Barlow.txt"):
    ok(f"licence {f} présente (OFL 1.1)", "SIL OPEN FONT LICENSE Version 1.1" in read("vendor", "fonts", f))
ok("three.module.js autonome (n'importe rien d'autre)", not re.search(r"^\s*import\s", read("vendor", "three", "three.module.js"), re.M))
ok("Dockerfile : vendor/ copié dans l'image", re.search(r"^COPY vendor \./vendor$", read("Dockerfile"), re.M) is not None)

# --- la page : rien n'est chargé hors du serveur (seule l'API publique de l'exchange est appelée par le navigateur)
page = read("index.html")
imap = json.loads(re.search(r'<script type="importmap">(.*?)</script>', page, re.S).group(1))["imports"]
ok("importmap : three servi par le dashboard", imap.get("three") == "/vendor/three/three.module.js" and imap["three"] in dash.VENDOR)
qr = re.search(r'sc\.src = "([^"]+)"', page)
ok("QR : qrcode-generator servi par le dashboard", qr is not None and qr.group(1) in dash.VENDOR)
m = re.search(r'sc\.integrity = "(sha512-[^"]+)"', page)
ok("QR : le fichier local correspond au SRI de la page", m is not None and sri(open(os.path.join(V, "qrcode-generator", "qrcode.min.js"), "rb").read(), "sha512") == m.group(1))
sheets = re.findall(r'<link[^>]+href="([^"]+)"[^>]*rel="stylesheet"|<link[^>]+rel="stylesheet"[^>]*href="([^"]+)"', page)
sheets = [a or b for a, b in sheets]
ok("feuilles de style : toutes locales (polices embarquées)", sheets == ["/vendor/fonts/fonts.css"])
fonts = re.findall(r"url\(([^)]+)\)", read("vendor", "fonts", "fonts.css"))
ok("fonts.css : 12 polices, toutes présentes", len(fonts) == 12 and all(f"/vendor/fonts/{f}" in dash.VENDOR for f in fonts))
CDN = re.compile(r"fonts\.googleapis|fonts\.gstatic|jsdelivr|cdnjs|unpkg|esm\.sh|skypack", re.I)
front = {"index.html": page, "sw.js": read("sw.js"), "fx.js": read("fx.js"), "fonts.css": read("vendor", "fonts", "fonts.css")}
for f in sorted(os.listdir(os.path.join(HERE, "character"))):
    if f.endswith(".js"):
        front[f"character/{f}"] = read("character", f)
ok("aucun CDN dans la page, le service worker, les effets ni le personnage", not [k for k, s in front.items() if CDN.search(s)])
hosts = set()
for s in (page, front["fx.js"]):
    hosts |= set(re.findall(r"""(?:fetch\(|src=|href=|import\(|url\()\s*["']?https?://([^/"'\s)]+)""", s))
ok(f"hôtes externes : l'API de l'exchange et le lien de recharge OpenRouter, rien d'autre ({', '.join(sorted(hosts))})",
   hosts <= {"api.hyperliquid.xyz", "openrouter.ai"})

# --- service : type, gzip pour le texte, ETag / 304
GZ = {"Accept-Encoding": "gzip"}
for path, ctype in (("/vendor/three/three.module.js", "text/javascript; charset=utf-8"), ("/vendor/qrcode-generator/qrcode.min.js", "text/javascript; charset=utf-8"),
                    ("/vendor/fonts/fonts.css", "text/css; charset=utf-8")):
    s, h, raw = req(path, GZ)
    body = gzip.decompress(raw) if h.get("content-encoding") == "gzip" else raw
    ok(f"{path} : 200 {ctype.split(';')[0]}, gzip, contenu exact", s == 200 and h.get("content-type") == ctype and h.get("content-encoding") == "gzip"
       and body == open(os.path.join(V, *path.split("/")[2:]), "rb").read())
    s2, h2, raw2 = req(path, dict(GZ, **{"If-None-Match": h.get("etag", "x")}))
    ok(f"{path} : revalidation 304 sans corps", s2 == 304 and raw2 == b"" and h.get("cache-control") == "no-cache")
s, h, raw = req("/vendor/fonts/chakra-petch-latin-700-normal.woff2", GZ)
ok("police woff2 : 200 font/woff2, jamais recompressée", s == 200 and h.get("content-type") == "font/woff2" and "content-encoding" not in h
   and raw == open(os.path.join(V, "fonts", "chakra-petch-latin-700-normal.woff2"), "rb").read())
ok("seuls .js/.css/.woff2 sont servis (pas les licences)", sorted({os.path.splitext(p)[1] for p in dash.VENDOR}) == [".css", ".js", ".woff2"]
   and len(dash.VENDOR) == 15)

# --- ce qui doit rester introuvable : traversée, encodages, fichiers non listés
secret = open(os.path.join(HERE, "dash.py"), "rb").read()[:200]
for path in ("/vendor/../dash.py", "/vendor/three/../../dash.py", "/vendor/%2e%2e/dash.py", "/vendor/three/%2e%2e/%2e%2e/dash.py",
             "/vendor/%2E%2E%2Fdash.py", "/vendor/three/..%2f..%2fdash.py", "/vendor/three/..\\..\\dash.py", "/vendor/..%5c..%5cdash.py",
             "/vendor/three/three.module.js/../../../dash.py", "/vendor//three/three.module.js", "/vendor/three/three.module.js/",
             "/vendor/three/three.module.js%00.png", "/vendor/fonts/./fonts.css", "/vendor/FONTS/fonts.css",
             "/vendor/three/LICENSE", "/vendor/fonts/LICENSE-Barlow.txt", "/vendor/", "/vendor", "/vendor/three",
             "/vendor/../../../../etc/passwd", "/vendor/../index.html"):
    s, h, raw = req(path)
    ok(f"refusé : {path}", s == 404 and secret not in raw and b"Permission is hereby" not in raw)
s, h, raw = req("/vendor/three/three.module.js?v=1")
ok("paramètres ignorés comme ailleurs (?v=…)", s == 200)

# --- la liste figée : un dossier de test avec un fichier hors des types et un lien symbolique vers l'extérieur
tmp = tempfile.mkdtemp()
os.makedirs(os.path.join(tmp, "a"))
open(os.path.join(tmp, "a", "x.js"), "w").close()
open(os.path.join(tmp, "a", "y.py"), "w").close()
try:
    os.symlink(os.path.join(HERE, "dash.py"), os.path.join(tmp, "a", "z.js"))
    linked = True
except (OSError, NotImplementedError):   # Windows sans droit de créer des liens
    linked = False
got = dash.vendor_files(tmp)
ok("vendor_files : seuls les types connus, liens symboliques écartés" + ("" if linked else " (lien non testé ici)"), list(got) == ["/vendor/a/x.js"])
shutil.rmtree(tmp, ignore_errors=True)

# --- le service worker : chaque fichier mis en cache existe et est servi ; plus aucun CDN dans sa logique
sw = read("sw.js")
cached = [p for name in ("SHELL", "VENDOR") for p in json.loads(re.search(rf"const {name} = (\[.*?\]);", sw).group(1))]
bad = [p for p in cached if req(p)[0] != 200]
ok(f"service worker : les {len(cached)} fichiers mis en cache à l'installation sont servis", not bad)
for p in bad:
    print("     absent :", p)
ok("service worker : /vendor/ gardé en cache (marche hors connexion)", 'url.pathname.startsWith("/vendor/")' in sw)

print("\n" + ("ÉCHEC" if ok.bad else "Tout est vert."))
sys.exit(1 if ok.bad else 0)
