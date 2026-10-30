"""שימוש משורת הפקודה:

    python -m hebsearch.cli search "הלך" תיקייה1 קובץ.docx --inflections
    python -m hebsearch.cli index תיקייה1
"""

import argparse
import os
import sys
import time

from .index import IndexDB, resolve_items
from .paths import default_db_path
from .search import SEG_MATCH, Searcher, SearchOptions


def _items(paths):
    return [(p, "folder" if os.path.isdir(p) else "file") for p in paths]


def _update(db, files, quiet=False):
    stale = db.stale_files(files)
    if stale:
        t0 = time.perf_counter()

        def prog(done, total, path):
            if not quiet:
                print(f"\r  מאנדקס {done}/{total}", end="", file=sys.stderr, flush=True)

        db.update(stale, progress=prog)
        if not quiet:
            print(f"\r  אונדקסו {len(stale)} קבצים ב-{time.perf_counter() - t0:.1f} ש'", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hebsearch")
    ap.add_argument("--db", default=default_db_path())
    sub = ap.add_subparsers(dest="cmd", required=True)
    ix = sub.add_parser("index")
    ix.add_argument("paths", nargs="+")
    se = sub.add_parser("search")
    se.add_argument("query")
    se.add_argument("paths", nargs="+")
    se.add_argument("--no-prefixes", action="store_true")
    se.add_argument("--inflections", action="store_true")
    se.add_argument("--ahevi", choices=["none", "vy", "all"], default="none")
    se.add_argument("--gap", type=int, default=0)
    se.add_argument("--paragraph", action="store_true")
    se.add_argument("--any-order", action="store_true")
    se.add_argument("--limit", type=int, default=50)
    args = ap.parse_args(argv)

    db = IndexDB(args.db)
    files = resolve_items(_items(args.paths))
    _update(db, files, quiet=args.cmd == "search")
    if args.cmd == "index":
        print(db.stats())
        return 0

    opts = SearchOptions(prefixes=not args.no_prefixes, inflections=args.inflections,
                         ahevi=args.ahevi, max_gap=args.gap, whole_paragraph=args.paragraph,
                         ordered=not args.any_order)
    searcher = Searcher(db)
    res = searcher.search(args.query, db.file_ids(files), opts)
    if res.message:
        print(res.message)
    print(f"{res.total} תוצאות ב-{len(res.files)} קבצים ({res.elapsed * 1000:.0f} מ\"ש)")
    if res.forms:
        print("צורות:", ", ".join(f"{w}({c})" for w, c in res.forms.most_common(15)))
    for h in res.hits[: args.limit]:
        searcher.materialize(h, res.highlight)
        snippet = "".join(f"[{t}]" if k == SEG_MATCH else t for t, k in h.snippet)
        print(f"\n{os.path.basename(h.path)} | {h.location}\n  {' '.join(snippet.split())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
