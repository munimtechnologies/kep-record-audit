#!/usr/bin/env python3
"""Kubernetes feature-gate stage census, run 1.

Reads every feature-gate page of the Kubernetes documentation (kubernetes/website,
one Markdown file per gate, with its alpha/beta/stable/deprecated stages and the
releases each stage covered, removed gates included) at one pinned commit, and
computes the pre-registered statistics in PREREG.md (H1-H4 and the descriptives).
Writes <out-dir>/summary.json and <out-dir>/gates.json (one row per gate).

Apache-2.0. Standard library only.
    python job.py --data-dir /data --out-dir /out --allow-net
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

REPO = "kubernetes/website"
API = f"https://api.github.com/repos/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}"
DIR = "content/en/docs/reference/command-line-tools-reference/feature-gates"
UA = "MV2-Munim-research/1.0 (mv2@munimtech.com; k8s-feature-gate-census)"
CACHE = "k8s-feature-gates.json"
PAUSE = 0.25

RANK = {"alpha": 0, "beta": 1, "stable": 2}
H1_WIN = (10, 18)
H2_OLD, H2_NEW, H2_K = (10, 18), (20, 32), 4
H3_OLD, H3_NEW = (14, 23), (24, 33)
H4_AGE = 8

TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$")
REMOVED_RE = re.compile(r"^removed:\s*true\b", re.I)
STAGES_RE = re.compile(r"^stages:\s*$")
ITEM_RE = re.compile(r"^\s*-\s*stage:\s*([A-Za-z]+)")
KEY_RE = re.compile(r"^\s+(\w+):\s*(.*?)\s*$")
VER_RE = re.compile(r"""^\s*["']?1\.(\d+)""")


# ---------------------------------------------------------------- helpers

def _share(k, n):
    return None if n == 0 else k / n


def hist(values):
    out = {}
    for v in values:
        k = str(v)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def ver(s):
    """'1.14' or '"1.14"' -> 14; anything else -> None."""
    m = VER_RE.match(str(s or ""))
    return int(m.group(1)) if m else None


def _stage_name(s):
    s = s.strip().lower()
    return "stable" if s == "ga" else s


def parse_gate(text):
    """Title, removed flag and stage list from one feature-gate page."""
    title, removed, stages, cur, in_st = None, False, [], None, False
    for line in text.splitlines():
        if title is None:
            m = TITLE_RE.match(line)
            if m:
                title = m.group(1).strip("\"'")
                continue
        if REMOVED_RE.match(line):
            removed, in_st = True, False
            continue
        if STAGES_RE.match(line):
            in_st = True
            continue
        if not in_st:
            continue
        if line.strip() == "---":
            in_st = False
            continue
        m = ITEM_RE.match(line)
        if m:
            cur = {"stage": _stage_name(m.group(1))}
            stages.append(cur)
            continue
        m = KEY_RE.match(line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2).strip("\"'")
            continue
        if line.strip() and not line[:1].isspace():
            in_st = False
    return {"name": title, "removed": removed, "stages": stages}


def facts(g):
    """First release of each stage, its default, entry stage, current stage, last release."""
    first, default, last, cur, cur_from = {}, {}, None, None, None
    for s in g["stages"]:
        st, v = s.get("stage"), ver(s.get("fromVersion"))
        if v is None:
            continue
        if st not in first or v < first[st]:
            first[st] = v
            default[st] = str(s.get("defaultValue", "")).lower() == "true"
        if cur_from is None or v >= cur_from:
            cur, cur_from = st, v
        for x in (v, ver(s.get("toVersion"))):
            if x is not None and (last is None or x > last):
                last = x
    entry = min(first, key=lambda k: (first[k], RANK.get(k, 9))) if first else None
    return {"name": g["name"], "removed": g["removed"], "first": first, "default": default,
            "entry": entry, "current": "removed" if g["removed"] else cur, "last": last}


def monotonic(f):
    seq = [f["first"][s] for s in ("alpha", "beta", "stable") if s in f["first"]]
    return all(a <= b for a, b in zip(seq, seq[1:]))


# ---------------------------------------------------------------- download

def get(url, tries=8):
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500, 502, 503, 504) and i < tries - 1:
                h = e.headers or {}
                wait, reset = h.get("Retry-After"), h.get("X-RateLimit-Reset")
                if wait and wait.isdigit():
                    pause = float(wait)
                elif reset and reset.isdigit() and h.get("X-RateLimit-Remaining") == "0":
                    pause = min(3700.0, max(5.0, int(reset) - time.time() + 5))
                else:
                    pause = 30.0 * (i + 1)
                time.sleep(pause)
                continue
            raise
        except (OSError, http.client.HTTPException):
            if i < tries - 1:
                time.sleep(30 * (i + 1))
                continue
            raise


def download():
    sha = json.loads(get(f"{API}/commits/main"))["sha"]
    parent_dir, leaf = DIR.rsplit("/", 1)
    parent = json.loads(get(f"{API}/contents/{parent_dir}?ref={sha}"))
    dsha = next(e["sha"] for e in parent if e.get("name") == leaf)
    tree = json.loads(get(f"{API}/git/trees/{dsha}"))
    names = sorted(e["path"] for e in tree.get("tree") or []
                   if e.get("type") == "blob" and e["path"].endswith(".md")
                   and not e["path"].startswith("_"))
    files = {}
    for i, name in enumerate(names):
        files[name] = get(f"{RAW}/{sha}/{DIR}/{name}").decode("utf-8")
        if i % 50 == 0:
            print(f"fetched {i + 1}/{len(names)}", file=sys.stderr, flush=True)
        time.sleep(PAUSE)
    return {"downloaded": dt.datetime.now(dt.timezone.utc).date().isoformat(),
            "commit": sha, "tree_truncated": bool(tree.get("truncated")), "files": files}


def load(data_dir, allow_net):
    path = os.path.join(data_dir, CACHE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    if not allow_net:
        sys.exit(f"no cache at {path} and --allow-net not given")
    blob = download()
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blob, fh)
    return blob


# ---------------------------------------------------------------- predictions

def in_win(v, win):
    return v is not None and win[0] <= v <= win[1]


def h1(F):
    rows = [f for f in F if in_win(f["first"].get("alpha"), H1_WIN)]
    grad = [f for f in rows if "stable" in f["first"]]
    fast = [f for f in grad if 0 <= f["first"]["stable"] - f["first"]["alpha"] <= 2]
    return {"alpha_from": list(H1_WIN), "n": len(rows), "graduated": len(grad),
            "fast": len(fast), "share_of_all": _share(len(fast), len(rows)),
            "share_of_graduated": _share(len(fast), len(grad))}


def stable_within(f, k):
    b, s = f["first"].get("beta"), f["first"].get("stable")
    return b is not None and s is not None and 0 <= s - b <= k


def h2(F, V):
    res = {}
    for name, win in (("old", H2_OLD), ("new", H2_NEW)):
        rows = [f for f in F if in_win(f["first"].get("beta"), win)]
        k = sum(1 for f in rows if stable_within(f, H2_K))
        res[name] = {"beta_from": list(win), "n": len(rows), "stable_within_4": k,
                     "share": _share(k, len(rows))}
    res["full_follow_up"] = V is not None and V >= H2_NEW[1] + H2_K
    return res


def h3(F):
    res = {}
    for name, win in (("old", H3_OLD), ("new", H3_NEW)):
        rows = [f for f in F if in_win(f["first"].get("beta"), win)]
        off = sum(1 for f in rows if not f["default"]["beta"])
        res[name] = {"beta_from": list(win), "n": len(rows), "default_off": off,
                     "share": _share(off, len(rows))}
    return res


def h4(F, V):
    rows = [f for f in F if f["current"] == "beta" and "beta" in f["first"]]
    old = [f for f in rows if V - f["first"]["beta"] >= H4_AGE]
    return {"n_current_beta": len(rows), "beta_8_plus_releases": len(old),
            "share": _share(len(old), len(rows))}


def grade(m):
    g = {}
    s = m["H1"]["share_of_graduated"]
    g["H1"] = "NULL" if s is None else ("HELD" if s <= 0.10 else "FAILED")
    o, n = m["H2"]["old"]["share"], m["H2"]["new"]["share"]
    g["H2"] = ("NULL" if o is None or n is None or not m["H2"]["full_follow_up"]
               else ("HELD" if n >= o + 0.10 else "FAILED"))
    o, n = m["H3"]["old"]["share"], m["H3"]["new"]["share"]
    g["H3"] = "NULL" if o is None or n is None else ("HELD" if n >= o + 0.10 else "FAILED")
    s = m["H4"]["share"]
    g["H4"] = "NULL" if s is None else ("HELD" if s >= 0.25 else "FAILED")
    return g


# ---------------------------------------------------------------- descriptives

def by_version(F, stage, pred, V, min_follow=0):
    """{release: [n gates whose first `stage` release is it, n of them satisfying pred]}."""
    out = {}
    for f in F:
        v = f["first"].get(stage)
        if v is None or V is None or v > V - min_follow:
            continue
        b = out.setdefault(v, [0, 0])
        b[0] += 1
        b[1] += 1 if pred(f) else 0
    return {str(k): out[k] for k in sorted(out)}


def descriptives(F, V):
    def diff(f, a, b):
        return f["first"][b] - f["first"][a]

    cur_beta = sorted((f for f in F if f["current"] == "beta" and "beta" in f["first"]),
                      key=lambda f: (f["first"]["beta"], f["name"] or ""))
    cur_alpha = sorted((f for f in F if f["current"] == "alpha" and "alpha" in f["first"]),
                       key=lambda f: (f["first"]["alpha"], f["name"] or ""))
    return {
        "entry_stage_hist": hist(f["entry"] for f in F),
        "current_stage_hist": hist(f["current"] for f in F),
        "non_monotonic": sorted(f["name"] or "" for f in F if not monotonic(f)),
        "alpha_from_hist": hist(f["first"]["alpha"] for f in F if "alpha" in f["first"]),
        "beta_from_hist": hist(f["first"]["beta"] for f in F if "beta" in f["first"]),
        "stable_from_hist": hist(f["first"]["stable"] for f in F if "stable" in f["first"]),
        "alpha_to_stable_hist": hist(diff(f, "alpha", "stable") for f in F
                                     if "alpha" in f["first"] and "stable" in f["first"]),
        "beta_to_stable_hist": hist(diff(f, "beta", "stable") for f in F
                                    if "beta" in f["first"] and "stable" in f["first"]),
        "stable_within_4_by_beta_from": by_version(F, "beta", lambda f: stable_within(f, H2_K),
                                                   V, H2_K),
        "beta_default_off_by_beta_from": by_version(F, "beta",
                                                    lambda f: not f["default"]["beta"], V),
        "abandoned_without_stable": sum(1 for f in F
                                        if f["removed"] and "stable" not in f["first"]),
        "oldest_current_beta": [[f["name"], f["first"]["beta"], f["default"]["beta"]]
                                for f in cur_beta[:15]],
        "oldest_current_alpha": [[f["name"], f["first"]["alpha"]] for f in cur_alpha[:15]],
    }


def compute(gates):
    F = [facts(g) for g in gates if g["stages"]]
    lasts = [f["last"] for f in F if f["last"] is not None]
    V = max(lasts) if lasts else None
    return {"n_gates": len(gates), "n_with_stages": len(F),
            "n_removed": sum(1 for f in F if f["removed"]), "V": V,
            "H1": h1(F), "H2": h2(F, V), "H3": h3(F), "H4": h4(F, V),
            "descriptives": descriptives(F, V)}, F


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/data")
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--allow-net", action="store_true")
    args = ap.parse_args()

    blob = load(args.data_dir, args.allow_net)
    gates = []
    for name, text in sorted(blob["files"].items()):
        g = parse_gate(text)
        g["name"] = g["name"] or name[:-3]
        gates.append(g)
    metrics, F = compute(gates)
    verdicts = grade(metrics)
    summary = {"data_source": f"https://github.com/{REPO}/tree/{blob['commit']}/{DIR}",
               "commit": blob["commit"], "snapshot_date": blob["downloaded"],
               "tree_truncated": blob["tree_truncated"], "metrics": metrics,
               "verdicts": verdicts}
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    with open(os.path.join(args.out_dir, "gates.json"), "w", encoding="utf-8") as fh:
        json.dump(sorted(F, key=lambda f: f["name"] or ""), fh, indent=1, sort_keys=True)
    print(json.dumps({"verdicts": verdicts, "V": metrics["V"], "n_gates": metrics["n_gates"],
                      "H1": metrics["H1"], "H2": metrics["H2"], "H3": metrics["H3"],
                      "H4": metrics["H4"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
