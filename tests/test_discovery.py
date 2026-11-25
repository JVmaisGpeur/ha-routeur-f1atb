"""Recherche réseau avec de vrais sockets locaux (port 80, nécessite les droits root).

Lancer : python3 tests/test_discovery.py
127.0.0.2 = routeur F1ATB (répond à /ajax_dataESP32), 127.0.0.3 = autre appareil web (404),
127.0.0.4 = adresse sans serveur web.
"""
import asyncio
import os
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "stubs"))
_pkg = types.ModuleType("f1atb_routeur")
_pkg.__path__ = [str(HERE.parent / "custom_components" / "f1atb_routeur")]
sys.modules["f1atb_routeur"] = _pkg

from f1atb_routeur import discovery as D  # noqa: E402
import test_parsers as T  # noqa: E402

REQUESTS: list[tuple[str, str]] = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok -", msg)


def server(body_for_path):
    async def handle(reader, writer):
        line = (await reader.readline()).decode()
        while (await reader.readline()) not in (b"\r\n", b""):
            pass
        path = line.split(" ")[1] if " " in line else "?"
        REQUESTS.append((writer.get_extra_info("sockname")[0], path))
        body = body_for_path(path)
        status = "200 OK" if body is not None else "404 Not Found"
        data = (body or "Not found").encode()
        writer.write(f"HTTP/1.1 {status}\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode() + data)
        await writer.drain()
        writer.close()
    return handle


class _Resp:
    def __init__(self, status, body):
        self.status = status
        self.content = types.SimpleNamespace(read=self._read)
        self._body = body

    async def _read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Get:
    """Mini client HTTP (le vrai aiohttp n'est pas installé ici)."""

    def __init__(self, url):
        rest = url.split("://", 1)[1]
        self.host, _, path = rest.partition("/")
        self.path = "/" + path

    async def __aenter__(self):
        r, w = await asyncio.open_connection(self.host, 80)
        w.write(f"GET {self.path} HTTP/1.1\r\nHost: {self.host}\r\n\r\n".encode())
        await w.drain()
        raw = await r.read()
        w.close()
        head, _, body = raw.partition(b"\r\n\r\n")
        return _Resp(int(head.split(b" ")[1]), body)

    async def __aexit__(self, *a):
        return False


async def main():
    if os.geteuid() != 0:
        print("ignoré : il faut les droits root pour écouter sur le port 80")
        return
    router = await asyncio.start_server(server(lambda p: T.ESP32_16 if p == "/ajax_dataESP32" else None), "127.0.0.2", 80)
    other = await asyncio.start_server(server(lambda p: None), "127.0.0.3", 80)

    async def fake_hosts(hass):
        return ["127.0.0.2", "127.0.0.3", "127.0.0.4"], ["127.0.0.0/24"]

    D.async_local_hosts = fake_hosts
    D.async_get_clientsession = lambda hass: types.SimpleNamespace(get=lambda url, **kw: _Get(url))
    async with router, other:
        res = await D.async_scan(None)
    check(res.found == ["127.0.0.2"], "routeur trouvé par sa réponse /ajax_dataESP32 (pas par le texte de sa page d'accueil)")
    check(res.tested == 3 and res.web == 2, "compte rendu : 3 adresses, 2 serveurs web")
    http = sorted(r for r in REQUESTS if r[1] != "?")
    check(http == [("127.0.0.2", "/ajax_dataESP32"), ("127.0.0.3", "/ajax_dataESP32")],
          "une seule lecture par serveur web, rien d'autre n'est appelé")
    check(sorted(r[0] for r in REQUESTS if r[1] == "?") == ["127.0.0.2", "127.0.0.3"],
          "1er temps : simple ouverture de connexion, aucune requête envoyée")
    print("\nRecherche réseau : tous les tests passent.")


asyncio.run(main())
