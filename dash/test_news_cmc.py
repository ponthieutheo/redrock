"""Test hors ligne de la source CoinMarketCap du dashboard (page sauvegardée, aucun appel réseau).
Lancer : python dash/test_news_cmc.py"""
import os, sys, tempfile, time, types

try:
    import defusedxml  # noqa: F401
except ImportError:       # présent dans l'image du dashboard, pas forcément sur le PC ; les flux RSS sont de toute façon coupés ici
    d = types.ModuleType("defusedxml"); d.ElementTree = types.ModuleType("defusedxml.ElementTree")
    sys.modules.update({"defusedxml": d, "defusedxml.ElementTree": d.ElementTree})

os.environ.update(HL_SUBACCOUNT="0x0", CHAT_KEY="secret", HERMES_API_KEY="hk", HERMES_URL="http://127.0.0.1:1")
sys.path.insert(0, os.path.dirname(__file__))
import dash

dash.DATA = tempfile.mkdtemp()
PAGE = open(os.path.join(os.path.dirname(__file__), "fixtures", "cmc_news_2026-10-13.html"), encoding="utf-8").read()


def ok(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        ok.bad = True
ok.bad = False


class Resp:
    def __init__(self, text, code=200):
        self.text, self.status_code, self.content = text, code, text.encode()


calls = []


def fake_get(url, **kw):
    calls.append(url)
    if "coinmarketcap.com" in url:
        return Resp(fake_get.page, fake_get.code)
    raise OSError("hors ligne")      # les flux RSS échouent : fetch_news doit continuer


fake_get.page, fake_get.code = PAGE, 200
dash.requests.get = fake_get

items = dash.parse_cmc_news(PAGE)
ok("la page sauvegardée donne 20 articles", len(items) == 20)
ok("champs : titre, lien https, date entière, média d'origine",
   all(i["title"] and i["link"].startswith("https://") and isinstance(i["ts"], int) and i["via"] for i in items))
ok("dates plausibles (2026)", all(1.78e9 < i["ts"] < 1.80e9 for i in items))

for name, bad in (("vide", ""), ("pas de script", "<html>rien</html>"), ("JSON cassé", '<script id="__NEXT_DATA__" type="application/json">{oups</script>'),
                  ("clé absente", '<script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>'),
                  ("newsFeed pas une liste", '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"newsFeed":5}}}</script>'),
                  ("date illisible", '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"newsFeed":[{"meta":{"title":"x","sourceUrl":"https://a","releasedAt":"hier"}}]}}}</script>')):
    try:
        r = dash.parse_cmc_news(bad)
        ok(f"page changée ({name}) : liste vide sans exception", r == [])
    except Exception as e:
        ok(f"page changée ({name}) : liste vide sans exception", False)

ok("lien non https ignoré", dash.parse_cmc_news('<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"newsFeed":[{"meta":{"title":"x","sourceUrl":"http://a","releasedAt":"2026-10-13T10:00:00.000Z"}}]}}}</script>') == [])

# fetch_news : CMC ajouté, les flux RSS en panne n'empêchent rien, une seule requête CMC (cache)
now = max(i["ts"] for i in items)
real_time = time.time
time.time = lambda: now + 600
try:
    dash._cmc.update(at=0.0, items=[])
    n = dash.fetch_news()
    ok("fetch_news contient CoinMarketCap malgré les RSS en panne", n and all(x["src"] == "CoinMarketCap" for x in n) and len(n) == 15)
    ok("articles triés du plus récent au plus ancien", [x["ts"] for x in n] == sorted((x["ts"] for x in n), reverse=True))
    n_cmc = sum("coinmarketcap" in u for u in calls)
    dash.fetch_news(); dash.fetch_news()
    ok("cache : pas de nouvelle requête CMC avant 15 min", sum("coinmarketcap" in u for u in calls) == n_cmc == 1)

    # après le cache, un 403 garde la dernière liste connue
    time.time = lambda: now + 600 + 1000
    fake_get.code = 403
    n2 = dash.fetch_news()
    ok("403 : on garde la dernière liste connue", len(n2) == 15)
    # page cassée : idem
    time.time = lambda: now + 600 + 2000
    fake_get.code, fake_get.page = 200, "<html>nouvelle mise en page</html>"
    ok("page changée : on garde la dernière liste connue", len(dash.fetch_news()) == 15)
    # tout est coupé dès le départ : liste vide, pas d'exception
    dash._cmc.update(at=0.0, items=[])
    time.time = lambda: now + 5000
    ok("rien de disponible : liste vide sans exception", dash.fetch_news() == [])
finally:
    time.time = real_time
sys.exit(1 if ok.bad else 0)
