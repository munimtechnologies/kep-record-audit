# kep-record-audit

A pre-registered audit of two public records Kubernetes keeps about each feature: the
milestones in each Kubernetes Enhancement Proposal's `kep.yaml` (kubernetes/enhancements), and
the stage history on each feature gate's page in the Kubernetes documentation
(kubernetes/website). How often do they agree on when a feature reached alpha, beta and stable?
When they differ, which way? How many KEPs still read "implementable" after the work shipped or
stopped?

By MV2 of Munim, Inc. (mv2@munimtech.com). The work was made with AI agents working in his
name. Code: Apache-2.0. Results and text: CC BY 4.0.

## Status

Pre-registered on 2026-10-31 (UTC), before any data was downloaded. Predictions P1-P4 and
their grading rules are in `PREREG.md`. Results will be added here once the run is graded,
including the predictions that fail.

## Files

- `PREREG.md`: question, data, definitions, predictions P1-P4, limits and prior work.
- `kep_audit.py`: downloads both records at pinned commits and computes everything in
  `PREREG.md`. Writes `summary.json` and `keps.json` (one row per KEP).
- `k8s_gates.py`: a verbatim copy of `job.py` from munimtechnologies/k8s-feature-gate-census,
  used to read the feature-gate pages the same way.
- `test_kep_audit.py`: tests on a hand-built fixture (expected values worked out in its
  docstring).

## Run it

    pip install pyyaml
    python -m unittest -v
    python kep_audit.py --data-dir ./data --out-dir ./out --allow-net

Python 3.10 or newer. PyYAML is needed only to read kep.yaml files.

## Limits

kep.yaml milestones are edited as plans change, so this compares the final recorded milestone
with the docs, not the original plan. A disagreement shows the records differ, not which one
is wrong. Older gates are often not listed in any KEP. This is an audit of records, not a
judgment of any feature or contributor.

Part of a series of lifecycle studies of standards and proposal processes by MV2 of Munim,
Inc.: IETF RFCs (rfc-obsolescence-survival, rfc-errata-hfdu-graveyard), Python PEPs
(pep-lifecycle-census), W3C specifications (w3c-spec-lifecycle), OpenJDK JEPs
(jep-lifecycle-census) and Kubernetes feature gates (k8s-feature-gate-census), all under
github.com/munimtechnologies.

-- MV2, Munim, Inc.
