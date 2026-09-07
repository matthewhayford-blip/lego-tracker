#!/usr/bin/env python3
"""Resolve every internal link in the built site; exit non-zero on any 404.

Exists because relative paths are easy to get subtly wrong in a site with a
market prefix, and the failure is silent -- the page renders, the link just
goes nowhere. Two real bugs were caught by this on 6 September:

  * nav links resolving to /retiring/ instead of /uk/retiring/, because one
    "up" path was being used for both market-relative content links and
    root-relative static assets;
  * `{{ rel }}` written inside an f-string body_html, which Jinja never
    re-renders, emitting the literal braces into the HTML.

Run after a build:  python tools/linkcheck.py [public_dir]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

HREF = re.compile(r'(?:href|src)="([^"]+)"')
SKIP = ("http://", "https://", "#", "mailto:", "tel:", "data:", "javascript:")


def check(root: Path) -> int:
    pages = list(root.rglob("*.html"))
    if not pages:
        print(f"no HTML under {root} -- run the build first")
        return 1

    broken, checked = [], 0
    for page in pages:
        rel_dir = page.parent.relative_to(root).as_posix()
        url_dir = "/" if rel_dir == "." else f"/{rel_dir}/"
        for href in HREF.findall(page.read_text(encoding="utf-8")):
            if href.startswith(SKIP):
                continue
            target = urlparse(urljoin(url_dir, href)).path
            checked += 1
            t = target.lstrip("/")
            cand = root / t
            if not (cand.is_file()
                    or (cand / "index.html").is_file()
                    or (root / (t + "index.html")).is_file()):
                broken.append((page.relative_to(root).as_posix(), href, target))

    print(f"checked {checked} internal links across {len(pages)} pages")
    if broken:
        print(f"BROKEN: {len(broken)}")
        seen = set()
        for src, href, target in broken:
            if (href, target) in seen:
                continue
            seen.add((href, target))
            print(f"  {src}\n    href={href!r} -> {target}")
            if len(seen) >= 20:
                print("  ...")
                break
        return 1
    print("all internal links resolve")
    return 0


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "public")
    raise SystemExit(check(out))
