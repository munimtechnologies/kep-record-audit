"""Tests for kep_audit.py on a hand-built fixture. Apache-2.0.

Docs gates (first release of each stage; V = newest release in the docs = 30, from A1):
    GA1  alpha 20, beta 22, stable 24 (to 25)     current stable
    GA2  alpha 20, beta 21, stable 23 (to 24)     current stable
    GA3  alpha 18, beta 19, stable 21 (to 22)     removed
    B1   alpha 22, beta 24 (no toVersion)         current beta
    A1   alpha 30                                 current alpha
    SH   alpha 26, beta 27                        current beta
    M1   alpha 20, stable 25                      current stable
    M2   alpha 21, stable 26                      current stable

KEPs (number, status, stage, latest, milestone a/b/s, gates):
    1   implemented   stable  24  20/22/24  [GA1]
    2   implementable stable  22  20/21/22  [GA2]
    3   implemented   stable  21  17/19/21  [GA3]
    4   implementable beta    24  22/24/-   [B1]
    5   implementable alpha   30  31/-/-    [A1]
    6   implementable alpha   26  26/-/-    [SH]   shared with 7
    7   provisional   alpha   27  26/-/-    [SH]   shared with 6
    8   implementable alpha   20  20/-/-    []
    9   implementable ''      -   -/-/-     [Nope] (not in the docs)
    10  implemented   stable  26  20/-/26   [M1, M2]

Sample S (one gate, in the docs, claimed by no other KEP) = KEPs 1-5.
Pairs (kep, docs) in S:
    1: a 20/20, b 22/22, s 24/24
    2: a 20/20, b 21/21, s 22/23  -> mismatch, docs later
    3: a 17/18 -> mismatch, docs later; b 19/19; s 21/21
    4: a 22/22, b 24/24
    5: a 31/30 -> mismatch, docs earlier
    alpha n 5 agree 3; beta n 4 agree 4; stable n 3 agree 2. Mismatches 3, docs later 2.
P1: stable n 3, agree 2 -> NULL (n < 20).
P1_all_gates: KEPs 1 (24=24), 2 (23 vs 22), 3 (21=21), 10 (max(25, 26)=26=26) -> n 4, agree 3.
    KEP 4 (B1 not stable), 5-7 (no stable milestone), 8 (no gates), 9 (gate not in docs) skip.
P2: mismatches 3, docs later 2 -> NULL (mismatches < 10).
P3: S KEPs whose gate is stable in the docs: 1, 2, 3; not implemented: 2 -> n 3, k 1.
P4: implementable KEPs 2, 4, 5, 6, 8, 9; 9 has no latest -> n 5, missing 1.
    Stale if latest <= 30 - 4 = 26: 2 (22), 4 (24), 6 (26), 8 (20) yes; 5 (30) no -> 4.
"""
import io
import os
import sys
import tarfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kep_audit as ka  # noqa: E402
import k8s_gates as kg  # noqa: E402

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def gate(name, stages, removed=False):
    return kg.facts({"name": name, "removed": removed,
                     "stages": [{"stage": s, "fromVersion": a, "toVersion": b}
                                for s, a, b in stages]})


def kep(num, status, stage, latest, ms, gates):
    doc = {"kep-number": num, "status": status, "stage": stage, "latest-milestone": latest,
           "milestone": ms,
           "feature-gates": [{"name": g, "components": ["kubelet"]} for g in gates]}
    return ka.kep_row(f"keps/sig-node/{num}-x/kep.yaml", doc)


def fixture():
    F = [
        gate("GA1", [("alpha", "1.20", "1.21"), ("beta", "1.22", "1.23"),
                     ("stable", "1.24", "1.25")]),
        gate("GA2", [("alpha", "1.20", "1.20"), ("beta", "1.21", "1.22"),
                     ("stable", "1.23", "1.24")]),
        gate("GA3", [("alpha", "1.18", "1.18"), ("beta", "1.19", "1.20"),
                     ("stable", "1.21", "1.22")], removed=True),
        gate("B1", [("alpha", "1.22", "1.23"), ("beta", "1.24", "")]),
        gate("A1", [("alpha", "1.30", "")]),
        gate("SH", [("alpha", "1.26", "1.26"), ("beta", "1.27", "")]),
        gate("M1", [("alpha", "1.20", "1.24"), ("stable", "1.25", "")]),
        gate("M2", [("alpha", "1.21", "1.25"), ("stable", "1.26", "")]),
    ]
    K = [
        kep("1", "implemented", "stable", "v1.24",
            {"alpha": "v1.20", "beta": "v1.22", "stable": "v1.24"}, ["GA1"]),
        kep("2", "implementable", "stable", "v1.22",
            {"alpha": "v1.20", "beta": "v1.21", "stable": "v1.22"}, ["GA2"]),
        kep("3", "implemented", "stable", "v1.21",
            {"alpha": "v1.17", "beta": "v1.19", "stable": "v1.21"}, ["GA3"]),
        kep("4", "implementable", "beta", "v1.24", {"alpha": "v1.22", "beta": "v1.24"}, ["B1"]),
        kep("5", "implementable", "alpha", "v1.30", {"alpha": "v1.31"}, ["A1"]),
        kep("6", "implementable", "alpha", "v1.26", {"alpha": "v1.26"}, ["SH"]),
        kep("7", "provisional", "alpha", "v1.27", {"alpha": "v1.26"}, ["SH"]),
        kep("8", "implementable", "alpha", "v1.20", {"alpha": "v1.20"}, []),
        kep("9", "implementable", "", None, None, ["Nope"]),
        kep("10", "implemented", "stable", "v1.26", {"alpha": "v1.20", "stable": "v1.26"},
            ["M1", "M2"]),
    ]
    return K, F


class TestParse(unittest.TestCase):
    def test_minor(self):
        self.assertEqual(ka.minor("v1.19"), 19)
        self.assertEqual(ka.minor('"v1.19"'), 19)
        self.assertEqual(ka.minor("1.9"), 9)
        self.assertEqual(ka.minor("v1.19.0"), 19)
        self.assertIsNone(ka.minor("TBD"))
        self.assertIsNone(ka.minor(""))
        self.assertIsNone(ka.minor(None))
        self.assertIsNone(ka.minor("v2.0"))

    def test_kep_row(self):
        r = ka.kep_row("keps/sig-apps/592-ttl-after-finish/kep.yaml",
                       {"status": "Implemented", "milestone": "",
                        "feature-gates": [{"name": "A"}, {"name": "A"}, "junk", {"x": 1}]})
        self.assertEqual(r["number"], "592")
        self.assertEqual(r["sig"], "sig-apps")
        self.assertEqual(r["status"], "implemented")
        self.assertEqual(r["ms"], {"alpha": None, "beta": None, "stable": None})
        self.assertEqual(r["gates"], ["A"])
        self.assertIsNone(r["latest"])

    @unittest.skipUnless(HAVE_YAML, "PyYAML not installed")
    def test_load_yaml(self):
        text = ("---\ntitle: X\nkep-number: 12\nlatest-milestone: 1.20\nmilestone:\n"
                "  alpha: \"v1.19\"\n  beta: 1.20\nfeature-gates:\n  - name: Foo\n"
                "    components:\n      - kubelet\nmetrics:\n---\n")
        doc = ka.load_yaml(text)
        r = ka.kep_row("keps/sig-node/12-x/kep.yaml", doc)
        self.assertEqual(r["number"], "12")
        self.assertEqual(r["latest"], 20)
        self.assertEqual(r["ms"], {"alpha": 19, "beta": 20, "stable": None})
        self.assertEqual(r["gates"], ["Foo"])

    def test_tar(self):
        buf = io.BytesIO()
        names = ["enhancements-abc/keps/sig-node/1-x/kep.yaml",
                 "enhancements-abc/keps/sig-node/1-x/README.md",
                 "enhancements-abc/keps/NNNN-kep-template/kep.yaml",
                 "enhancements-abc/keps/prod-readiness/sig-node/1.yaml"]
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for name in names:
                data = b"title: x\n"
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        files = ka.kep_files_from_tar(buf.getvalue())
        self.assertEqual(sorted(files), ["keps/sig-node/1-x/kep.yaml"])
        self.assertEqual(files["keps/sig-node/1-x/kep.yaml"], "title: x\n")


class TestCompute(unittest.TestCase):
    def setUp(self):
        K, F = fixture()
        self.m, self.rows = ka.compute(K, F)

    def test_sample_and_v(self):
        self.assertEqual(self.m["V"], 30)
        self.assertEqual(self.m["n_sample"], 5)
        self.assertEqual(sorted(r["number"] for r in self.rows if r["in_sample"]),
                         ["1", "2", "3", "4", "5"])

    def test_p1(self):
        self.assertEqual(self.m["P1"], {"n": 3, "agree": 2, "share": 2 / 3})
        self.assertEqual(self.m["P1_all_gates"], {"n": 4, "agree": 3, "share": 0.75})

    def test_p2(self):
        self.assertEqual(self.m["P2"], {"n_pairs": 12, "mismatches": 3, "docs_later": 2,
                                        "share": 2 / 3})

    def test_p3(self):
        p = self.m["P3"]
        self.assertEqual((p["n"], p["not_implemented"]), (3, 1))
        self.assertEqual(p["status_hist"], {"implementable": 1})

    def test_p4(self):
        self.assertEqual(self.m["P4"], {"V": 30, "n_implementable": 6, "missing_latest": 1,
                                        "n": 5, "stale": 4, "share": 0.8})

    def test_descriptives(self):
        d = self.m["descriptives"]
        self.assertEqual(d["status_hist"],
                         {"implementable": 6, "implemented": 3, "provisional": 1})
        self.assertEqual(d["unmatched_gate_names"], ["Nope"])
        self.assertEqual(d["shared_gates"], [["SH", ["6", "7"]]])
        self.assertEqual(d["n_listed_in_docs"], 8)
        bs = d["agreement_by_stage"]
        self.assertEqual((bs["alpha"]["n"], bs["alpha"]["agree"]), (5, 3))
        self.assertEqual((bs["beta"]["n"], bs["beta"]["agree"]), (4, 4))
        self.assertEqual((bs["stable"]["n"], bs["stable"]["agree"]), (3, 2))
        self.assertEqual(bs["alpha"]["diff_hist"], {"-1": 1, "0": 3, "1": 1})
        self.assertEqual(d["kep_stage_vs_docs_current"],
                         {"alpha|alpha": 1, "beta|beta": 1, "stable|removed": 1,
                          "stable|stable": 2})
        self.assertEqual(d["docs_coverage_by_entry_release"],
                         {"18": [1, 1], "20": [3, 3], "21": [1, 1], "22": [1, 1],
                          "26": [1, 1], "30": [1, 1]})

    def test_fixture_verdicts_null(self):
        g = ka.grade(self.m)
        self.assertEqual(g, {"P1": "NULL", "P1_all_gates": "NULL", "P2": "NULL",
                             "P3": "NULL", "P4": "NULL"})


class TestGrade(unittest.TestCase):
    def m(self, p1, p1a, p2, p3, p4):
        return {"P1": {"n": 40, "share": p1}, "P1_all_gates": {"n": 40, "share": p1a},
                "P2": {"mismatches": 10, "share": p2}, "P3": {"n": 20, "share": p3},
                "P4": {"n": 20, "share": p4}}

    def test_thresholds(self):
        self.assertEqual(ka.grade(self.m(0.85, 0.84, 0.60, 0.15, 0.30)),
                         {"P1": "HELD", "P1_all_gates": "FAILED", "P2": "HELD",
                          "P3": "HELD", "P4": "HELD"})
        self.assertEqual(ka.grade(self.m(0.5, 0.9, 0.59, 0.14, 0.29)),
                         {"P1": "FAILED", "P1_all_gates": "HELD", "P2": "FAILED",
                          "P3": "FAILED", "P4": "FAILED"})


if __name__ == "__main__":
    unittest.main()
