#!/usr/bin/env python3
"""NEO Golf Data — static dev server.

Adds the one rewrite the prototype needs:
    /player/{playerCode}            -> player.html
    /player/{playerCode}/hole/{id}  -> player.html   (reserved hole-detail route)
Production hosting only needs the same rewrite rule (see vercel.json / _redirects).
"""
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PLAYER_ROUTE = re.compile(r"^/player/[^/]+(/hole/[^/]+)?/?$")


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if PLAYER_ROUTE.match(clean):
            path = "/player.html"
        return super().translate_path(path)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
    print("NEO Golf Data → http://localhost:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
