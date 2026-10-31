# Pre-registration: KEP record audit, run 1

By MV2 of Munim, Inc. (mv2@munimtech.com), made with AI agents working in his name. Filed
2026-10-31 (UTC), before any data was downloaded or counted. Code: Apache-2.0. Text: CC BY 4.0.

## Question

Kubernetes keeps two public records of when a feature moved through alpha, beta and stable:

1. the Kubernetes Enhancement Proposal's own metadata, `kep.yaml` in kubernetes/enhancements
   (`status`, `stage`, `latest-milestone`, `milestone: {alpha, beta, stable}` and the
   `feature-gates` the KEP adds), and
2. the feature-gate pages of the Kubernetes documentation in kubernetes/website, which list
   each gate's stages and the release each stage started (`fromVersion`).

How often do the two agree, which way do they disagree, and how many KEP records are left
behind after the work ships or stops?

## Data

- Every `keps/sig-*/*/kep.yaml` in kubernetes/enhancements at the current `master` commit
  (one tarball from codeload.github.com, commit hash recorded). The template and the
  prod-readiness files are not KEPs and are skipped. A file that does not parse is listed in
  `parse_errors`, never dropped silently.
- Every feature-gate page in kubernetes/website, read with the code of
  munimtechnologies/k8s-feature-gate-census (`k8s_gates.py` is a verbatim copy of its
  `job.py`), at the current `main` commit (hash recorded).
- kep.yaml is read with PyYAML's BaseLoader, so every value stays a string (an unquoted
  `1.20` stays "1.20" instead of becoming the number 1.2). A milestone is the minor version
  of `v1.N` or `1.N`; anything else counts as missing.

## Definitions

- **Docs stage release** of a gate: the earliest `fromVersion` of that stage on its page.
- **V**: the newest release that appears anywhere on the docs pages.
- **Sample S**: KEPs that list exactly one feature gate, where that gate has a docs page with
  stages and no other KEP lists the same gate name (exact, case-sensitive match).
- **Pair**: a KEP in S and a stage (alpha, beta, stable) for which both the kep.yaml milestone
  and the docs stage release exist. It agrees if the two releases are equal.

## Predictions

- **P1 (stable dates agree).** Among stable pairs, at least 85% agree.
  HELD if share >= 0.85; NULL if fewer than 20 pairs.
  Robustness (`P1_all_gates`, same rule): all KEPs with at least one listed gate in the docs,
  all of those gates stable there, docs release = the latest first-stable among them. If P1
  and P1_all_gates disagree, P1 is reported as not robust.
- **P2 (disagreements are unrecorded slips).** Across all three stages, of the pairs that
  disagree, at least 60% have the docs release LATER than the kep.yaml milestone (the KEP
  names a release the stage did not reach).
  HELD if share >= 0.60; NULL if fewer than 10 disagreeing pairs.
- **P3 (shipped but not closed).** Among KEPs in S whose gate reached stable in the docs, at
  least 15% do not have `status: implemented`.
  HELD if share >= 0.15; NULL if fewer than 20 KEPs.
- **P4 (stale implementable KEPs).** Among KEPs with `status: implementable` and a readable
  `latest-milestone`, at least 30% have `latest-milestone` <= V - 4 (no recorded work in the
  last four releases). KEPs with no readable latest-milestone are counted separately.
  HELD if share >= 0.30; NULL if fewer than 20 KEPs.

How blind these are: the author has read the KEP template, the KEP process README and four
individual records (KEP 277, 592, 753 and the template) and one docs page
(EphemeralContainers). KEP 277's milestones match its docs page exactly. No aggregate of
either record was seen. The thresholds are guesses from how the release team works: it
checks kep.yaml at each Enhancements Freeze, so a slip is recorded only if the KEP opts in
again.

## Descriptives (no predictions)

Status, stage and latest-milestone histograms; how many KEPs list gates; gate names listed by
KEPs that have no docs page (and how many differ only by case); gates listed by more than one
KEP; per docs entry release, how many gates are listed by any KEP; agreement and the
docs-minus-KEP difference per stage; every disagreeing pair; KEP `stage` against the gate's
current docs stage for S. `keps.json` has one row per KEP with its docs stages.

## Limits

kep.yaml files are edited when plans change, so this compares the FINAL recorded milestone
with the docs, not the original plan; the original targets need the git history of each file
(a possible follow-up). The docs are a summary kept by people too: a disagreement says the two
records differ, not which one is wrong, and the run does not decide that. Gates added before
the `feature-gates` field existed (around v1.19-1.21) are often not listed in any KEP, so S
leans to newer features. Release numbers are not calendar time. This is an audit of public
records, not a judgment of any feature or contributor.

## Prior work searched (2026-10-31)

Kepler (github.com/mrueg/kepler), a KEP browser whose dashboard shows status counts, a stage
funnel, a time-to-stable histogram and a milestone heatmap from kep.yaml alone; it does not
compare kep.yaml with the docs. arXiv 2604.15872 measures whole feature-gate lifespans from
code, not KEP records. munimtechnologies/k8s-feature-gate-census (pre-registered, queued) uses
the docs alone. The original KEP process document lists metrics it says should be tracked
(time in each state, rejection rate, orphaned KEPs); no published report of them was found.
No published comparison of KEP milestones with the documented gate stages was found.
