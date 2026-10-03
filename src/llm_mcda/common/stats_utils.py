"""Shared statistical helpers.

Only routines that were verified to be behaviourally identical across their
former call sites live here. Variants that differ (for example
`run_rag_ablation_experiments.holm_correct`, whose `p_holm` column is NOT
passed through a running maximum) are deliberately kept where they are.

These helpers operate on p-values only. They never see metric scores, so the
1928 failed-score sentinel cannot reach them; callers are responsible for
excluding sentinel scores before computing any p-value.
"""

import numpy as np


def holm_adjust(pvals):
    """Holm-Bonferroni adjusted p-values with the running-maximum pass.

    Order is preserved. Non-finite inputs (NaN) are excluded from the family
    and returned as NaN. Ties are ordered with a stable (mergesort) sort. Each
    raw p is scaled by (k - rank), capped at 1.0, and a running maximum over
    the ascending ranks enforces monotone adjusted values.

    This is the routine formerly inlined in
    `scripts/validation/significance_testing.run_wilcoxon` and defined as
    `holm()` in `scripts/paper_pipeline/emit_per_model_pvalues.py`.
    """
    p = np.asarray(pvals, dtype=float)
    out = np.full(p.shape, np.nan)
    idx = np.where(np.isfinite(p))[0]
    if len(idx) == 0:
        return out
    order = idx[np.argsort(p[idx], kind="mergesort")]
    k = len(order)
    running = 0.0
    for i, j in enumerate(order):
        adj = min(p[j] * (k - i), 1.0)
        running = max(running, adj)   # enforce monotonicity
        out[j] = running
    return out
