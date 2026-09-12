"""Audit .env files: report keys, duplicates, and value-status only - NEVER values."""
import io
import os
import sys

PLACEHOLDER_MARKERS = ("your-", "change-me", "example", "placeholder", "platform-", "xxx", "todo", "test")


def classify(value):
    v = value.strip().strip('"').strip("'")
    if v == "":
        return "EMPTY"
    lv = v.lower()
    if any(m in lv for m in PLACEHOLDER_MARKERS):
        return "PLACEHOLDER-LIKE"
    return "SET"


def audit(path):
    if not os.path.exists(path):
        print(f"--- {path}: NOT FOUND")
        return
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    entries = []
    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            print(f"  NON-KEY=VALUE line {i}: {line[:40]!r}")
            continue
        key, _, value = line.partition("=")
        entries.append((i, key.strip(), classify(value)))
    print(f"--- {path}")
    print(f"  key=value lines: {len(entries)}")
    keys = {}
    for i, key, status in entries:
        keys.setdefault(key, []).append((i, status))
    dupes = {k: v for k, v in keys.items() if len(v) > 1}
    print(f"  unique keys: {len(keys)} | duplicated keys: {len(dupes)}")
    for k, occ in sorted(dupes.items()):
        statuses = "/".join(s for _, s in occ)
        print(f"  DUP  {k}: lines {[n for n, _ in occ]} value-status [{statuses}]")
    for k in sorted(keys):
        occ = keys[k]
        line_nos = [n for n, _ in occ]
        statuses = [s for _, s in occ]
        print(f"  KEY  {k}: lines {line_nos} -> {statuses}")
    print()


for p in sys.argv[1:]:
    audit(p)
