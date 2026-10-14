"""Test hors ligne du cache HTTP du dashboard : gzip, ETag / 304, Cache-Control, /api/state calculé une fois par TTL.
Lancer : python -I -X utf8 dash/test_perf.py"""
import gzip, http.client, json, os, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))


class FakeHermes(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for t in ("Salut ", "Alex"):
            self.wfile.write(("data: " + json.dumps({"id": "chatcmpl-ab12", "choices": [{"delta": {"content": t}}]}) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


hp = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermes)
threading.Thread(target=hp.serve_forever, daemon=True).start()
os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL=f"http://127.0.0.1:{hp.server_port}")
sys.path.insert(0, HERE)
import dash

dash.DATA = tempfile.mkdtemp()
FIX = os.path.join(HERE, "fixtures", "state_demo.json")
base = json.load(open(FIX, encoding="utf-8"))
calls = {"n": 0}
cur = {"st": base}


def fake_state():
    calls["n"] += 1
    return json.loads(json.dumps(cur["st"]))


dash.state = fake_state
dash.inbox_unread = lambda: 0
dash.PERSO = ""   # personnage par défaut (RedRock) : la page est servie telle quelle
dp = ThreadingHTTPServer(("127.0.0.1", 0), dash.H)
threading.Thread(target=dp.serve_forever, daemon=True).start()


def req(method, path, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", dp.server_port, timeout=20)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    raw = r.read()
    h = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, h, raw


def unzip(h, raw):
    return gzip.decompress(raw) if h.get("content-encoding") == "gzip" else raw


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True
ok.bad = False

GZ, ID = {"Accept-Encoding": "gzip, deflate"}, {"Accept-Encoding": "identity"}
index = open(os.path.join(HERE, "index.html"), "rb").read()

# --- fichiers statiques
s, h, raw = req("GET", "/", GZ)
ok("/ : 200 gzip", s == 200 and h.get("content-encoding") == "gzip" and unzip(h, raw) == index)
ok("/ : compressé bien plus petit", len(raw) < len(index) * 0.4)
ok("/ : Vary, ETag, Cache-Control no-cache", h.get("vary") == "Accept-Encoding" and h.get("etag", "").startswith('W/"') and h.get("cache-control") == "no-cache")
ok("/ : Content-Length exact", int(h.get("content-length", -1)) == len(raw))
tag = h["etag"]
s, h, raw = req("GET", "/", ID)
ok("/ sans gzip demandé : non compressé, même contenu", s == 200 and "content-encoding" not in h and raw == index and h.get("etag") == tag)
s, h, raw = req("GET", "/", {"Accept-Encoding": "gzip;q=0"})
ok("gzip;q=0 : non compressé", s == 200 and "content-encoding" not in h)
s, h, raw = req("GET", "/", dict(GZ, **{"If-None-Match": tag}))
ok("/ : If-None-Match → 304 sans corps", s == 304 and raw == b"" and h.get("etag") == tag)
s, h, raw = req("GET", "/", dict(GZ, **{"If-None-Match": '"autre", ' + tag[2:]}))
ok("/ : liste If-None-Match + comparaison faible → 304", s == 304)
s, h, raw = req("GET", "/", dict(GZ, **{"If-None-Match": 'W/"perime"'}))
ok("/ : ETag périmé → 200", s == 200)
s, h, raw = req("GET", "/icon-192.png", GZ)
ok("PNG : jamais gzip, ETag présent", s == 200 and "content-encoding" not in h and h.get("etag") and raw[:4] == b"\x89PNG")
s, h, raw = req("GET", "/sw.js", GZ)
ok("sw.js : no-cache + ETag", s == 200 and h.get("cache-control") == "no-cache" and h.get("etag"))
chars = [f for f in os.listdir(os.path.join(HERE, "character")) if f.endswith(".js")] if os.path.isdir(os.path.join(HERE, "character")) else []
if chars:
    s, h, raw = req("GET", f"/character/{chars[0]}", GZ)
    ok("/character/*.js servi en JS", s == 200 and "javascript" in h.get("content-type", "") and unzip(h, raw) == open(os.path.join(HERE, "character", chars[0]), "rb").read())
libre = open(os.path.join(HERE, "character-libre", "boulon.js"), "rb").read()
s, h, raw = req("GET", "/character-libre/boulon.js", GZ)
ok("/character-libre/boulon.js servi en JS, gzip", s == 200 and "javascript" in h.get("content-type", "") and h.get("content-encoding") == "gzip" and unzip(h, raw) == libre)
for bad in ("/character/../dash.py", "/character/LICENSE", "/character/x.py", "/character/inexistant.js", "/dash.py",
            "/character-libre/../dash.py", "/character-libre/LICENSE", "/character-libre/README.md", "/character-libre/inexistant.js", "/character-autre/boulon.js"):
    s, h, raw = req("GET", bad, GZ)
    ok(f"{bad} : 404 no-store", s == 404 and "no-store" in h.get("cache-control", ""))
# perso libre (CHARACTER=libre, ou character/ absent) : la page est marquée <html data-perso="libre">, avec son propre ETag
dash.PERSO = "libre"
s, h, raw = req("GET", "/", GZ)
page = unzip(h, raw)
ok("perso libre : <html data-perso=\"libre\">, le reste inchangé", s == 200 and page.startswith(index.split(b"<html", 1)[0] + b'<html data-perso="libre"')
   and page.replace(b' data-perso="libre"', b"", 1) == index)
ok("perso libre : ETag distinct, 304 ensuite", h.get("etag") and h.get("etag") != tag and req("GET", "/", dict(GZ, **{"If-None-Match": h["etag"]}))[0] == 304)
dash.PERSO = ""
ok("personnage par défaut : la page d'origine", unzip(*req("GET", "/", GZ)[1:]) == index)

# --- /api/state
calls["n"] = 0
s, h, raw = req("GET", "/api/state", GZ)
st = json.loads(unzip(h, raw))
ok("/api/state : 200 gzip, même format", s == 200 and h.get("content-encoding") == "gzip" and st["generation"] == base["generation"] and "trades" in st and "inbox_unread" in st)
full_len = len(unzip(h, raw))
stag = h.get("etag")
s, h, raw = req("GET", "/api/state", GZ)
ok("/api/state : calculé une seule fois pendant le TTL", calls["n"] == 1 and h.get("etag") == stag)
s, h, raw = req("GET", "/api/state", dict(GZ, **{"If-None-Match": stag}))
ok("/api/state : 304 si inchangé", s == 304 and raw == b"")
cur["st"] = dict(base, now="2030-01-01T00:00:00+00:00", hl_at="2030-01-01T00:00:00+00:00")
dash.state_invalidate()
s, h, raw = req("GET", "/api/state", dict(GZ, **{"If-None-Match": stag}))
ok("/api/state : seuls now/hl_at changent → 304 (même minute)", s == 304 and calls["n"] == 2)
cur["st"] = dict(base, equity=(base.get("equity") or 0) + 1)
dash.state_invalidate()
s, h, raw = req("GET", "/api/state", dict(GZ, **{"If-None-Match": stag}))
ok("/api/state : contenu changé → 200 et nouvel ETag", s == 200 and h.get("etag") != stag)
dash._state_cache["t"] = time.time() - dash.STATE_TTL - 1
req("GET", "/api/state", GZ)
ok("/api/state : recalculé après le TTL", calls["n"] == 4)
s, h, raw = req("GET", "/api/state?lite=1", GZ)
lt = json.loads(unzip(h, raw))
ok("/api/state?lite=1 : même format, tableaux raccourcis", s == 200 and lt.get("lite") is True and lt["lessons"] == [] and len(lt["journal"]) <= 10
   and len([t for t in lt["trades"] if t.get("status") != "open"]) <= 15 and len(lt["equity_curve"]) <= 300 and lt["generation"] == base["generation"])
ok("/api/state?lite=1 : ETag distinct de la version complète", h.get("etag") and h.get("etag") != dash._state_cache["full"]["etag"])
big = dict(base, equity_curve=[{"ts": i, "equity": i} for i in range(1742)])
cur["st"] = big; dash.state_invalidate()
s, h, raw = req("GET", "/api/state?lite=1", GZ)
lc = json.loads(unzip(h, raw))["equity_curve"]
ok("lite : courbe sous-échantillonnée à 300 points, premier et dernier gardés", len(lc) == 300 and lc[0]["ts"] == 0 and lc[-1]["ts"] == 1741)
dash.inbox_unread = lambda: 7
dash.state_invalidate()
s, h, raw = req("GET", "/api/state", GZ)
ok("state_invalidate : compteur de non-lus à jour tout de suite", json.loads(unzip(h, raw))["inbox_unread"] == 7)

# --- endpoints authentifiés et flux
K = dict(GZ, **{"X-Chat-Key": "secret"})
s, h, raw = req("GET", "/api/chat/history", K)
ok("/api/chat/history : private, no-store, pas d'ETag", s == 200 and h.get("cache-control") == "private, no-store" and "etag" not in h)
s, h, raw = req("GET", "/api/inbox", K)
ok("/api/inbox : private, no-store", s == 200 and "no-store" in h.get("cache-control", "") and "etag" not in h)
s, h, raw = req("POST", "/api/inbox/read", dict(K, **{"Content-Type": "application/json"}), json.dumps({"all": True}))
ok("POST /api/inbox/read : no-store", s == 200 and "no-store" in h.get("cache-control", ""))
s, h, raw = req("POST", "/api/cmd", dict(K, **{"Content-Type": "application/json"}), json.dumps({"command": "help"}))
ok("POST /api/cmd : no-store", s == 200 and "no-store" in h.get("cache-control", "") and json.loads(unzip(h, raw)).get("ok") is True)
s, h, raw = req("GET", "/api/inbox", GZ)
ok("/api/inbox sans clé : 401 no-store", s == 401 and "no-store" in h.get("cache-control", ""))
s, h, raw = req("POST", "/api/chat", dict(K, **{"Content-Type": "application/json"}), json.dumps({"message": "coucou"}))
ok("/api/chat (SSE) : jamais compressé, no-store", s == 200 and "content-encoding" not in h and h.get("content-type") == "text/event-stream"
   and "no-store" in h.get("cache-control", "") and b'"delta": "Salut "' in raw)

# --- JSON publics
dash.market = lambda: {"majors": [{"coin": "BTC", "chg": 1.0}]}
s, h, raw = req("GET", "/api/market", GZ)
ok("petit JSON public : non compressé (< 1 Ko), ETag + no-cache", s == 200 and "content-encoding" not in h and h.get("etag") and h.get("cache-control") == "no-cache")
s, h, raw = req("GET", "/api/market", dict(GZ, **{"If-None-Match": h["etag"]}))
ok("JSON public inchangé → 304", s == 304)
dash.market = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
s, h, raw = req("GET", "/api/market", GZ)
ok("erreur 500 : no-store", s == 500 and "no-store" in h.get("cache-control", ""))

# --- gain mesuré
s, h, raw = req("GET", "/", GZ)
cur["st"] = base; dash.state_invalidate()
s2, h2, raw2 = req("GET", "/api/state", GZ)
print(f"MESURE  / : {len(index)} → {len(raw)} octets ({len(raw) / len(index):.0%}) ; /api/state (fixture) : {len(unzip(h2, raw2))} → {len(raw2)} octets ({len(raw2) / len(unzip(h2, raw2)):.0%})")
print("\nÉCHEC" if ok.bad else "\nTout est vert.")
sys.exit(1 if ok.bad else 0)
