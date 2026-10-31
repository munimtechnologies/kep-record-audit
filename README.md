# kep-record-audit

A pre-registered audit of two public records Kubernetes keeps about each feature: the
milestones in each Kubernetes Enhancement Proposal's `kep.yaml` (kubernetes/enhancements), and
the stage history on each feature gate's page in the Kubernetes documentation
(kubernetes/website). How often do they agree on when a feature reached alpha, beta and stable?
When they differ, which way? How many KEPs still read "implementable" after the work shipped or
stopped?

By MV2 of Munim, Inc. (mv2@munimtech.com). The work was made with AI agents working in his
name. Code: Apache-2.0. Results and text: CC BY 4.0. The records it reads are (c) The
Kubernetes Authors (kubernetes/enhancements Apache-2.0, documentation CC BY 4.0).

## Results, run 1 (graded against PREREG.md)

`PREREG.md` was committed on 2026-10-31 (UTC) by the run that filed the job, before any data
was downloaded. The job ran once later that day in a sealed container (tests passed first).
It read all 643 `kep.yaml` files at kubernetes/enhancements commit a904b50 (none failed to
parse) and the 489 feature-gate pages with stages at kubernetes/website commit c4055f1. The
newest release in the docs is 1.37 (V = 37).

392 KEPs list feature gates: 450 distinct names, of which 339 have a docs page. The sample S
(a KEP listing exactly one gate that has a docs page and that no other KEP lists) has 238
KEPs. Three predictions held and one failed.

- **P1 HELD: the two records almost always agree on when a feature went stable.** 147 of 150
  stable pairs (98.0%) give the same release (rule: at least 85%). The robustness check over
  all KEPs whose listed gates are all stable gives 162 of 172 (94.2%), so P1 is robust.
  Agreement is 200 of 213 (93.9%) for alpha and 189 of 195 (96.9%) for beta.
- **P2 FAILED: disagreements are not mostly unrecorded slips.** Of the 22 pairs (all stages)
  that disagree, the docs give a LATER release than the KEP in only 7 (31.8%; rule: at least
  60%). In the other 15 the docs put the stage EARLIER than the KEP says.
- **P3 HELD.** Of 150 KEPs in S whose gate is stable in the docs, 26 (17.3%) still read
  `status: implementable` instead of `implemented` (rule: at least 15%).
- **P4 HELD.** Of 256 KEPs with `status: implementable` and a readable `latest-milestone`, 96
  (37.5%) name 1.33 or earlier, so no work has been recorded on them for four releases (rule:
  at least 30%). 19 more implementable KEPs have no readable latest-milestone.

How blind: the author had read four KEP records and one docs page, and no aggregate of
either record, before filing (stated in `PREREG.md`).

### Why P2 failed: a gate and a KEP mark different moments

Three disagreeing pairs were checked by hand on 2026-10-31 against the live files and the
Kubernetes source:

- **KEP-3466, ComponentSLIs (stable: KEP 1.29, docs 1.32).** The gate's GA entry in
  component-base (release-1.32) is version 1.32, and a code comment there says the feature
  reached GA in 1.29 but the gate was not updated until 1.32. The KEP records the feature,
  the docs record the gate, and both are right.
- **KEP-3962, MutatingAdmissionPolicy (alpha: KEP 1.32, docs 1.30).** The docs page itself
  says the gate existed but had no effect in 1.30 and 1.31. The gate came before the feature.
- **KEP-5683, NodeLifecycleConditions (alpha: KEP 1.38, docs 1.37).** `kube_features.go` on
  release-1.37 defines the gate as alpha from 1.37, off by default, citing KEP 5683, while
  the KEP (status implementable) gives 1.38 as its alpha and latest milestone. Whether the
  1.37 gate already does anything was not checked.

Three more mismatches come from one KEP: KEP-19 is the CronJob API (its kep.yaml gives alpha
1.4, beta 1.8, stable 1.21), while the gate it lists, CronJobControllerV2, belongs to the
rewritten controller (docs: 1.20, 1.21, 1.22). So most disagreements are not errors in
either record. They arise because a feature gate can be registered before its feature is
usable, can outlive or lag it, or can belong to a later rewrite. This is an explanation
from a few cases, not a tested rule.

### Records that are simply off (exploratory, found after grading)

- Five KEPs have a `status` outside the seven values in the KEP template: KEP-2625
  (`imlpemented`, a typo), KEP-5000 (the template's own placeholder list
  `provisional|implementable|implemented|deferred|rejected|withdrawn|replaced`, with stage
  `alpha|beta|stable` and every milestone `TBD`), KEP-1753 (`implemented (alpha)`), KEP-4153
  (`superseded`) and KEP-281 (`removed`). KEP-2625 and KEP-5000 were re-read live on
  2026-10-31.
- Five gate names listed in KEPs differ from the docs page name only by letter case (for
  example `setHostnameAsFQDN` in KEP-1797 and `InPlacePodVerticalScalingExclusiveCPUS` in
  KEP-6122). Some KEPs fill the gate field with a placeholder (`NA`, `None`, `n/a`) or a
  pattern (`CSIMigration{vendor}`).
- 13 gate names are listed by more than one KEP (for example CPUManagerPolicyAlphaOptions by
  seven KEPs), so a gate is not always one feature.

Descriptives: `status` values are implemented 296, implementable 275, provisional 47,
withdrawn 11, replaced 5, rejected 3, deferred 1, plus the five above. 90 KEPs give 1.38 (the
release in progress) as their latest milestone, and 110 give none that can be read.

## Limits

kep.yaml milestones are edited as plans change, so this compares the final recorded milestone
with the docs, not the original plan. A disagreement shows the records differ, not which one
is wrong; the three hand checks above are the only cases where that was looked into. Gates
added before the `feature-gates` field existed are often not listed in any KEP, so S leans to
newer features. Release numbers are not calendar time. This is an audit of public records,
not a judgment of any feature or contributor.

## Files

- `PREREG.md`: question, data, definitions, predictions P1-P4, limits and prior work.
- `kep_audit.py`: downloads both records at pinned commits and computes everything in
  `PREREG.md`. Writes `summary.json` and `keps.json` (one row per KEP).
- `k8s_gates.py`: a verbatim copy of `job.py` from munimtechnologies/k8s-feature-gate-census,
  used to read the feature-gate pages the same way.
- `test_kep_audit.py`: tests on a hand-built fixture (expected values worked out in its
  docstring).
- `results/run1-summary.json`: the graded output with every descriptive and all 22
  disagreeing pairs.
- `results/keps.json`: one row per KEP (status, stage, milestones, listed gates and their
  docs stages). It contains no names of people.

## Run it

    pip install pyyaml
    python -m unittest -v
    python kep_audit.py --data-dir ./data --out-dir ./out --allow-net

Python 3.10 or newer. PyYAML is needed only to read kep.yaml files.

Part of a series of lifecycle studies of standards and proposal processes by MV2 of Munim,
Inc.: IETF RFCs (rfc-obsolescence-survival, rfc-errata-hfdu-graveyard), Python PEPs
(pep-lifecycle-census), W3C specifications (w3c-spec-lifecycle), OpenJDK JEPs
(jep-lifecycle-census) and Kubernetes feature gates (k8s-feature-gate-census), all under
github.com/munimtechnologies.

-- MV2, Munim, Inc.
