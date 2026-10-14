#!/usr/bin/env python3
"""Appelle un outil du broker RedRock (serveur MCP, transport « streamable HTTP ») avec la seule bibliothèque standard.

    python3 broker_call.py account
    python3 broker_call.py history '{"limit": 5}'

Sert aux scripts de veille (sentinelle, post-mortem, docteur) que Hermes lance à chaque tick sans réveiller l'IA, et
à l'agent pour joindre un outil du broker depuis son terminal. Adresse du broker : variable REDROCK_BROKER_URL, sinon
l'url du serveur MCP du broker lue dans config.yaml de Hermes, sinon http://broker:8765/mcp.

Échange : initialize (le serveur rend un en-tête mcp-session-id), notifications/initialized, tools/call, puis DELETE
de la session (sinon le broker garde chaque session ouverte en mémoire). Réponses en JSON ou en flux SSE.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://broker:8765/mcp"
PROTOCOL = "2025-03-26"
HOME = os.environ.get("HERMES_HOME") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BrokerError(Exception):
    """Broker injoignable, réponse illisible, ou outil en erreur."""


def broker_url(config=None):
    """REDROCK_BROKER_URL, sinon l'url du serveur MCP du broker dans config.yaml (lecture ligne à ligne, sans YAML)."""
    env = os.environ.get("REDROCK_BROKER_URL", "").strip()
    if env:
        return env
    found, inside, name = [], False, ""
    try:
        with open(config or os.path.join(HOME, "config.yaml"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return DEFAULT_URL
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            inside = line.split(":", 1)[0].strip() == "mcp_servers"
            continue
        if not inside:
            continue
        m = re.match(r"^\s{1,4}([\w.-]+):\s*$", line)
        if m:
            name = m.group(1)
            continue
        m = re.match(r"""^\s+url:\s*["']?(https?://[^"'\s#]+)""", line)
        if m:
            found.append((name, m.group(1)))
    for n, u in found:
        if "broker" in n.lower():
            return u
    return found[0][1] if found else DEFAULT_URL


_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # réseau interne : jamais de proxy


def _messages(resp):
    """Messages JSON-RPC d'une réponse : un objet JSON, une liste, ou un flux SSE (lignes « data: »)."""
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in ctype:
        data = []
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("data:"):
                data.append(line[5:].lstrip(" "))
            elif not line and data:
                yield json.loads("\n".join(data))
                data = []
        if data:
            yield json.loads("\n".join(data))
        return
    body = resp.read()
    if not body.strip():
        return
    obj = json.loads(body.decode("utf-8", "replace"))
    for m in obj if isinstance(obj, list) else [obj]:
        yield m


class Session:
    """Une session MCP avec le broker (à fermer : with Session() as s: s.call("account"))."""

    def __init__(self, url=None, timeout=30):
        self.url, self.timeout = url or broker_url(), timeout
        self.sid, self.version, self._id = None, PROTOCOL, 0

    def _post(self, payload, timeout=None):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
            headers["MCP-Protocol-Version"] = self.version
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            return _opener.open(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as e:
            raise BrokerError(f"HTTP {e.code} sur {payload.get('method')}") from None
        except (urllib.error.URLError, OSError) as e:
            raise BrokerError(f"broker injoignable ({getattr(e, 'reason', e)})") from None

    def _request(self, method, params, timeout=None):
        self._id += 1
        rid = self._id
        resp = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}, timeout)
        with resp:
            if method == "initialize":
                self.sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
            try:
                for m in _messages(resp):
                    if isinstance(m, dict) and m.get("id") == rid:
                        if m.get("error"):
                            raise BrokerError(f"{method} : {m['error'].get('message', m['error'])}")
                        return m.get("result") or {}
            except (ValueError, OSError) as e:
                raise BrokerError(f"réponse illisible à {method} ({e})") from None
        raise BrokerError(f"pas de réponse à {method}")

    def open(self):
        r = self._request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                         "clientInfo": {"name": "redrock-veille", "version": "1"}})
        self.version = r.get("protocolVersion") or PROTOCOL
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}).close()
        return self

    def call(self, tool, args=None, timeout=None):
        """Texte renvoyé par l'outil (BrokerError si l'outil signale une erreur)."""
        if self.sid is None:
            self.open()
        r = self._request("tools/call", {"name": tool, "arguments": args or {}}, timeout)
        text = "\n".join(c.get("text", "") for c in r.get("content") or [] if c.get("type") == "text")
        if r.get("isError"):
            raise BrokerError(f"{tool} : {text[:300] or 'erreur'}")
        return text

    def call_json(self, tool, args=None, timeout=None):
        try:
            return json.loads(self.call(tool, args, timeout))
        except ValueError:
            raise BrokerError(f"{tool} : réponse non JSON") from None

    def close(self):
        if self.sid:
            req = urllib.request.Request(self.url, method="DELETE",
                                         headers={"Mcp-Session-Id": self.sid, "MCP-Protocol-Version": self.version})
            try:
                _opener.open(req, timeout=5).close()
            except Exception:
                pass
            self.sid = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def call(tool, args=None, url=None, timeout=30):
    with Session(url, timeout) as s:
        return s.call(tool, args)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip().split("\n\n")[1])
        return 0 if len(argv) >= 2 else 2
    try:
        args = json.loads(argv[2]) if len(argv) > 2 else {}
        if not isinstance(args, dict):
            raise ValueError("les arguments doivent être un objet JSON")
    except ValueError as e:
        print(f"arguments invalides : {e}", file=sys.stderr)
        return 2
    try:
        print(call(argv[1], args))
    except BrokerError as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
