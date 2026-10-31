#!/usr/bin/env python3
"""KEP record audit, run 1.

Compares what each Kubernetes Enhancement Proposal's kep.yaml says (status, stage, latest
milestone, the release of each stage, its feature gates) with the stage history that the
Kubernetes documentation gives for the same feature gates, and computes the pre-registered
statistics in PREREG.md (P1-P4, the P1 robustness check and the descriptives).
Writes <out-dir>/summary.json and <out-dir>/keps.json (one row per KEP).

The feature-gate pages are read with k8s_gates.py, a verbatim copy of job.py from
github.com/munimtechnologies/k8s-feature-gate-census.

Apache-2.0. Loading kep.yaml needs PyYAML; everything else is standard library.
    python kep_audit.py --data-dir /data --out-dir /out --allow-net
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import tarfile

import k8s_gates as kg

REPO = "kubernetes/enhancements"
API = f"https://api.github.com/repos/{REPO}"
TARBALL = "https://codeload.github.com/" + REPO + "/tar.gz/{sha}"
CACHE = "k8s-keps.json"

STAGES = ("alpha", "beta", "stable")
KEP_PATH_RE = re.compile(r"^[^/]+/(keps/sig-[^/]+/[^/]+/kep\.yaml)$")
MS_RE = re.compile(r"^v?1\.(\d+)")

MIN_N = 20        # P1, P3, P4 are NULL below this many cases
MIN_MIS = 10      # P2 is NULL below this many mismatches
P1_MIN = 0.85
P2_MIN = 0.60
P3_MIN = 0.15
P4_MIN = 0.30
P4_AGE = 4

_share = kg._share
hist = kg.hist


# ---------------------------------------------------------------- parsing

def minor(s):
    """'v1.19', '1.19', '"v1.19"', 'v1.19.0' -> 19; anything else -> None."""
    if s is None or isinstance(s, (dict, list)):
        return None
    m = MS_RE.match(str(s).strip().strip("\"'"))
    return int(m.group(1)) if m else None


def load_yaml(text):
    """First mapping document of a kep.yaml. Every scalar stays a string (BaseLoader),
    so an unquoted 1.20 is read as '1.20', not the float 1.2."""
    import yaml
    for doc in yaml.load_all(text, Loader=yaml.BaseLoader):
        if isinstance(doc, dict):
            return doc
    return None


def kep_row(path, doc):
    ms = doc.get("milestone")
    ms = ms if isinstance(ms, dict) else {}
    fg = doc.get("feature-gates")
    names = []
    if isinstance(fg, list):
        for g in fg:
            n = g.get("name") if isinstance(g, dict) else None
            if isinstance(n, str) and n.strip() and n.strip() not in names:
                names.append(n.strip())
    number = str(doc.get("kep-number") or "").strip() or path.split("/")[2].split("-")[0]
    return {"path": path, "number": number, "sig": path.split("/")[1],
            "status": str(doc.get("status") or "").strip().lower(),
            "stage": str(doc.get("stage") or "").strip().lower(),
            "latest": minor(doc.get("latest-milestone")),
            "ms": {s: minor(ms.get(s)) for s in STAGES},
            "created": str(doc.get("creation-date") or "")[:10],
            "gates": names}


# ---------------------------------------------------------------- download

def kep_files_from_tar(raw):
    """{'keps/sig-x/NNNN-name/kep.yaml': text} from a GitHub tar.gz of the repo."""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            mm = KEP_PATH_RE.match(m.name)
            if mm:
                files[mm.group(1)] = tf.extractfile(m).read().decode("utf-8", "replace")
    return files


def download_keps():
    sha = json.loads(kg.get(f"{API}/commits/master"))["sha"]
    raw = kg.get(TARBALL.format(sha=sha))
    return {"downloaded": dt.datetime.now(dt.timezone.utc).date().isoformat(),
            "commit": sha, "tarball_bytes": len(raw), "files": kep_files_from_tar(raw)}


def load_keps(data_dir, allow_net):
    path = os.path.join(data_dir, CACHE)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    if not allow_net:
        sys.exit(f"no cache at {path} and --allow-net not given")
    blob = download_keps()
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(blob, fh)
    return blob


# ---------------------------------------------------------------- predictions

def p1(pairs):
    st = [p for p in pairs if p["stage"] == "stable"]
    agree = sum(1 for p in st if p["kep"] == p["docs"])
    return {"n": len(st), "agree": agree, "share": _share(agree, len(st))}


def p1_all_gates(keps, G):
    """Robustness for P1: every KEP with at least one listed gate in the docs, all of them
    stable there; the docs stable release is the latest of its gates' first stable."""
    n = agree = 0
    for k in keps:
        fs = [G[g] for g in k["gates"] if g in G]
        if not fs or k["ms"]["stable"] is None or any("stable" not in f["first"] for f in fs):
            continue
        n += 1
        agree += 1 if max(f["first"]["stable"] for f in fs) == k["ms"]["stable"] else 0
    return {"n": n, "agree": agree, "share": _share(agree, n)}


def p2(pairs):
    mis = [p for p in pairs if p["kep"] != p["docs"]]
    later = sum(1 for p in mis if p["docs"] > p["kep"])
    return {"n_pairs": len(pairs), "mismatches": len(mis), "docs_later": later,
            "share": _share(later, len(mis))}


def p3(S, G):
    rows = [k for k in S if "stable" in G[k["gates"][0]]["first"]]
    open_ = [k for k in rows if k["status"] != "implemented"]
    return {"n": len(rows), "not_implemented": len(open_),
            "share": _share(len(open_), len(rows)),
            "status_hist": hist(k["status"] for k in open_)}


def p4(keps, V):
    rows = [k for k in keps if k["status"] == "implementable"]
    known = [k for k in rows if k["latest"] is not None]
    stale = [k for k in known if V is not None and k["latest"] <= V - P4_AGE]
    return {"V": V, "n_implementable": len(rows), "missing_latest": len(rows) - len(known),
            "n": len(known), "stale": len(stale), "share": _share(len(stale), len(known))}


def _rule(p, n_key, floor, minimum):
    if p[n_key] < floor or p["share"] is None:
        return "NULL"
    return "HELD" if p["share"] >= minimum else "FAILED"


def grade(m):
    return {"P1": _rule(m["P1"], "n", MIN_N, P1_MIN),
            "P1_all_gates": _rule(m["P1_all_gates"], "n", MIN_N, P1_MIN),
            "P2": _rule(m["P2"], "mismatches", MIN_MIS, P2_MIN),
            "P3": _rule(m["P3"], "n", MIN_N, P3_MIN),
            "P4": _rule(m["P4"], "n", MIN_N, P4_MIN)}


# ---------------------------------------------------------------- compute

def compute(keps, F):
    G = {f["name"]: f for f in F if f["name"]}
    lasts = [f["last"] for f in F if f["last"] is not None]
    V = max(lasts) if lasts else None
    claims = {}
    for k in keps:
        for g in k["gates"]:
            claims.setdefault(g, []).append(k["number"])
    S = [k for k in keps if len(k["gates"]) == 1 and k["gates"][0] in G
         and len(claims[k["gates"][0]]) == 1]
    pairs = []
    for k in S:
        f = G[k["gates"][0]]
        for s in STAGES:
            a, b = k["ms"][s], f["first"].get(s)
            if a is not None and b is not None:
                pairs.append({"number": k["number"], "gate": f["name"], "stage": s,
                              "kep": a, "docs": b})

    by_stage = {}
    for s in STAGES:
        ps = [p for p in pairs if p["stage"] == s]
        by_stage[s] = {"n": len(ps), "agree": sum(1 for p in ps if p["kep"] == p["docs"]),
                       "diff_hist": hist(p["docs"] - p["kep"] for p in ps)}
    lower = {name.lower() for name in G}
    listed = sorted(claims)
    unmatched = [g for g in listed if g not in G]
    cov = {}
    for f in F:
        if not f["first"]:
            continue
        b = cov.setdefault(min(f["first"].values()), [0, 0])
        b[0] += 1
        b[1] += 1 if f["name"] in claims else 0

    metrics = {
        "n_keps": len(keps), "n_docs_gates": len(F), "V": V, "n_sample": len(S),
        "P1": p1(pairs), "P1_all_gates": p1_all_gates(keps, G), "P2": p2(pairs),
        "P3": p3(S, G), "P4": p4(keps, V),
        "descriptives": {
            "status_hist": hist(k["status"] for k in keps),
            "stage_hist": hist(k["stage"] for k in keps),
            "latest_hist": hist(k["latest"] for k in keps),
            "n_keps_with_gates": sum(1 for k in keps if k["gates"]),
            "n_gate_names_listed": len(listed),
            "n_listed_in_docs": len(listed) - len(unmatched),
            "unmatched_gate_names": unmatched,
            "case_only_mismatches": [g for g in unmatched if g.lower() in lower],
            "shared_gates": [[g, claims[g]] for g in listed if len(claims[g]) > 1],
            "docs_coverage_by_entry_release": {str(v): cov[v] for v in sorted(cov)},
            "agreement_by_stage": by_stage,
            "mismatches": [p for p in pairs if p["kep"] != p["docs"]],
            "kep_stage_vs_docs_current": hist(f"{k['stage']}|{G[k['gates'][0]]['current']}"
                                              for k in S),
        },
    }
    in_s = {id(k) for k in S}
    rows = []
    for k in keps:
        r = dict(k)
        r["in_sample"] = id(k) in in_s
        r["docs"] = {g: {"first": G[g]["first"], "current": G[g]["current"]}
                     for g in k["gates"] if g in G}
        rows.append(r)
    return metrics, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/data")
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--allow-net", action="store_true")
    args = ap.parse_args()

    gblob = kg.load(args.data_dir, args.allow_net)
    kblob = load_keps(args.data_dir, args.allow_net)
    gates = []
    for name, text in sorted(gblob["files"].items()):
        g = kg.parse_gate(text)
        g["name"] = g["name"] or name[:-3]
        gates.append(g)
    F = [kg.facts(g) for g in gates if g["stages"]]
    keps, errors = [], []
    for path, text in sorted(kblob["files"].items()):
        try:
            doc = load_yaml(text)
        except Exception as e:  # report every file that does not parse, never drop silently
            errors.append([path, type(e).__name__])
            continue
        if not isinstance(doc, dict):
            errors.append([path, "not a mapping"])
            continue
        keps.append(kep_row(path, doc))
    metrics, rows = compute(keps, F)
    metrics["n_kep_files"] = len(kblob["files"])
    metrics["parse_errors"] = errors
    verdicts = grade(metrics)
    summary = {"kep_source": f"https://github.com/{REPO}/tree/{kblob['commit']}/keps",
               "kep_commit": kblob["commit"], "kep_snapshot_date": kblob["downloaded"],
               "docs_source": f"https://github.com/{kg.REPO}/tree/{gblob['commit']}/{kg.DIR}",
               "docs_commit": gblob["commit"], "docs_snapshot_date": gblob["downloaded"],
               "docs_tree_truncated": gblob["tree_truncated"], "metrics": metrics,
               "verdicts": verdicts}
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    with open(os.path.join(args.out_dir, "keps.json"), "w", encoding="utf-8") as fh:
        json.dump(sorted(rows, key=lambda r: r["path"]), fh, indent=1, sort_keys=True)
    print(json.dumps({"verdicts": verdicts, "V": metrics["V"], "n_keps": metrics["n_keps"],
                      "n_sample": metrics["n_sample"], "P1": metrics["P1"],
                      "P1_all_gates": metrics["P1_all_gates"], "P2": metrics["P2"],
                      "P3": metrics["P3"], "P4": metrics["P4"],
                      "parse_errors": len(errors)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
