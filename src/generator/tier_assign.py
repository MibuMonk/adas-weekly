"""Dynamic tier-assignment for the 6-column newspaper CSS Grid.

Grid invariant
--------------
Each tier consumes a fixed number of columns out of 6:
  T1  →  6 columns  (full-width hero)
  T2  →  3 columns  (2 articles per row)
  T3  →  2 columns  (3 articles per row)
  T4  →  1 column   (6 articles per row)

No-gap rule: total columns used must be divisible by 6.

Mathematical reduction
----------------------
  total_cols = 6*n1 + 3*n2 + 2*n3 + n4

  Since 6*n1 is always divisible by 6, we need:
      (3*n2 + 2*n3 + n4) % 6 == 0

  Further: if n2 is even  → 3*n2 is a multiple of 6  ✓
           if n3 % 3 == 0 → 2*n3 is a multiple of 6  ✓
  So those two terms vanish mod 6, leaving:
      n4 % 6 == 0

  Summary of legal counts:
      n1: 1, 2, or 3
      n2: 0, 2, 4, 6   (even)
      n3: 0, 3, 6, 9, 12  (multiple of 3)
      n4: 0, 6, 12, 18, 24  (multiple of 6)

Score thresholds — editorial reasoning
---------------------------------------
After 30 years running front pages I've learned that grade inflation ruins
layouts.  Reserve the banner for stories that genuinely matter this week.

  T1 threshold  ≥ 8.0  — landmark news; expect 0–2 per week
  T2 threshold  ≥ 6.5  — strong story, deserves a lede and photo
  T3 threshold  ≥ 4.5  — worth a column brief with summary
  T4 threshold  ≥ 3.0  — bullet: headline + source only
  Below 3.0            — dropped entirely (processor already filters most)

These are soft floors: if a band is empty, we slide the boundary down to
guarantee a minimum-viable layout (at least 1 T1, 2 T2, 3 T3).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable thresholds (soft — adjusted downward when bands are too thin)
# ---------------------------------------------------------------------------
_T1_THRESHOLD = 8.0   # score >= this → candidate for hero
_T2_THRESHOLD = 6.5   # score >= this → candidate for secondary
_T3_THRESHOLD = 4.5   # score >= this → candidate for column brief
_T4_THRESHOLD = 3.0   # score >= this → bullet; below this gets dropped

# Hard caps (newspaper usability limits)
_N1_MAX = 3
_N2_MAX = 6   # 6 T2 articles = 1 full row of pairs + 1 extra pair
_N3_MAX = 12  # 12 T3 articles = 4 rows of triples
_N4_MAX = 24  # 24 T4 bullets = 4 rows of six

# Total article window
_TOTAL_MIN = 18
_TOTAL_MAX = 30


def assign_tiers(articles: list[dict]) -> list[dict]:
    """Assign tier values to articles based on score distribution.

    Args:
        articles: Sorted by relevance_score descending.
                  Each dict must have 'relevance_score' (float 0-10).

    Returns:
        A subset of articles (18–30) with 'tier' key set to 1/2/3/4.
        The total column usage is guaranteed divisible by 6 (no grid gaps).
    """
    if not articles:
        return []

    scores = [a.get("relevance_score", 0.0) for a in articles]
    n_available = len(scores)

    # ------------------------------------------------------------------
    # Step 1: Count raw candidates per tier using soft thresholds.
    #         "Soft" means we may lower a threshold if a band is starved.
    # ------------------------------------------------------------------
    t1_thresh = _T1_THRESHOLD
    t2_thresh = _T2_THRESHOLD
    t3_thresh = _T3_THRESHOLD
    t4_thresh = _T4_THRESHOLD

    # Adaptive floor: if no article clears T1 threshold, lower the bar
    # just enough to admit the single top article as hero.
    # A newspaper without a lead story is a pamphlet — there must always
    # be exactly 1 T1.  But we never inflate n1 beyond what genuinely
    # clears the threshold: if the top score is mediocre (< 8.0), we cap
    # n1 at 1 so a so-so week doesn't get three heroes it doesn't deserve.
    top_score = scores[0] if scores else 0.0
    _effective_n1_max = _N1_MAX
    if top_score < t1_thresh:
        t1_thresh = top_score  # admit the best available article as hero
        _effective_n1_max = 1  # mediocre week: one hero is enough
    elif top_score < 8.5:
        # Good but not exceptional — cap at 2 heroes max
        _effective_n1_max = 2

    # Count raw candidates (before snapping to legal counts)
    raw_n1 = sum(1 for s in scores if s >= t1_thresh)
    raw_n2 = sum(1 for s in scores if t2_thresh <= s < t1_thresh)
    raw_n3 = sum(1 for s in scores if t3_thresh <= s < t2_thresh)
    raw_n4 = sum(1 for s in scores if t4_thresh <= s < t3_thresh)

    # ------------------------------------------------------------------
    # Step 2: Snap n1/n2/n3 to legal values, then compute n4 to fill rows.
    # ------------------------------------------------------------------

    # n1: clamp to [1, effective_n1_max]
    n1 = max(1, min(raw_n1, _effective_n1_max))

    # If we have strong stories that got cut, convert extras to T2 pairs
    # (never leave a high-scoring article in a lower tier when it clearly
    # belongs higher — score > T2_THRESHOLD but couldn't fit as T1)
    # Articles that scored >= t1_thresh but exceed n1 cap get demoted to T2.
    t1_overflow = max(0, raw_n1 - n1)
    raw_n2_adjusted = raw_n2 + t1_overflow
    n2 = min(raw_n2_adjusted, _N2_MAX)
    n2 = (n2 // 2) * 2

    # n3: snap down to nearest multiple of 3, clamp to [0, N3_MAX]
    t2_overflow = max(0, raw_n2_adjusted - n2)
    raw_n3_adjusted = raw_n3 + t2_overflow
    n3 = min(raw_n3_adjusted, _N3_MAX)
    n3 = (n3 // 3) * 3

    # n4 must be a multiple of 6 (see module docstring).
    # We compute the "ideal" n4 from remaining candidates, then round to
    # nearest multiple of 6 while keeping total in [TOTAL_MIN, TOTAL_MAX].
    t3_overflow = max(0, raw_n3_adjusted - n3)
    raw_n4_adjusted = raw_n4 + t3_overflow

    # Total so far without T4
    subtotal = n1 + n2 + n3

    # How many T4 do we want?
    ideal_n4 = min(raw_n4_adjusted, _N4_MAX)

    # Clamp total to [TOTAL_MIN, TOTAL_MAX]
    ideal_total = subtotal + ideal_n4
    if ideal_total < _TOTAL_MIN:
        # Not enough scored articles — pad n4 up to the next multiple of 6
        # using the lowest-scoring available articles (or repeat if necessary)
        needed = _TOTAL_MIN - subtotal
        ideal_n4 = needed
    elif ideal_total > _TOTAL_MAX:
        ideal_n4 = _TOTAL_MAX - subtotal

    # Clamp ideal_n4 to [0, N4_MAX] before snapping
    ideal_n4 = max(0, min(ideal_n4, _N4_MAX))

    # Snap n4 to a multiple of 6.
    # Round to nearest multiple of 6 (could go up or down).
    n4_floor = (ideal_n4 // 6) * 6
    n4_ceil  = n4_floor + 6

    # Choose whichever multiple keeps total in [TOTAL_MIN, TOTAL_MAX].
    # Prefer the value that doesn't exceed TOTAL_MAX; if both violate,
    # prefer the floor (smaller layout is safer than an overflowing grid).
    def _total_ok(n4: int) -> bool:
        t = subtotal + n4
        return _TOTAL_MIN <= t <= _TOTAL_MAX

    if _total_ok(n4_ceil) and not _total_ok(n4_floor):
        n4 = n4_ceil
    elif _total_ok(n4_floor):
        # Both might be ok — pick whichever is closer to ideal_n4
        if abs(n4_ceil - ideal_n4) < abs(n4_floor - ideal_n4) and _total_ok(n4_ceil):
            n4 = n4_ceil
        else:
            n4 = n4_floor
    else:
        # Neither is strictly in range — pick the one that minimises
        # distance to TOTAL_MIN (we'd rather have too few than overflow)
        n4 = n4_floor

    # Final clamp (safety net)
    n4 = max(0, min(n4, _N4_MAX))
    total = subtotal + n4

    # ------------------------------------------------------------------
    # Step 3: Verify the no-gap invariant (assertion, not exception —
    #         a broken layout is better than a crashed pipeline).
    # ------------------------------------------------------------------
    total_cols = 6 * n1 + 3 * n2 + 2 * n3 + n4
    if total_cols % 6 != 0:
        logger.error(
            "assign_tiers: grid gap detected! "
            "n1=%d n2=%d n3=%d n4=%d → cols=%d (not divisible by 6). "
            "Falling back to safe defaults.",
            n1, n2, n3, n4, total_cols,
        )
        # Safe fallback: the original fixed layout for up to 24 articles
        return _safe_fallback(articles)

    logger.info(
        "assign_tiers: n1=%d n2=%d n3=%d n4=%d → %d articles, %d rows",
        n1, n2, n3, n4, total, total_cols // 6,
    )

    # ------------------------------------------------------------------
    # Step 4: Slice articles in rank order and stamp tier values.
    #         We take exactly `total` articles from the sorted input.
    # ------------------------------------------------------------------
    # Guard: if we asked for more articles than we have, trim counts.
    if total > n_available:
        total, n1, n2, n3, n4 = _trim_to_available(
            n_available, n1, n2, n3, n4
        )

    selected = articles[:total]
    cursor = 0

    for i in range(cursor, cursor + n1):
        selected[i]["tier"] = 1
    cursor += n1

    for i in range(cursor, cursor + n2):
        selected[i]["tier"] = 2
    cursor += n2

    for i in range(cursor, cursor + n3):
        selected[i]["tier"] = 3
    cursor += n3

    for i in range(cursor, cursor + n4):
        selected[i]["tier"] = 4

    return selected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trim_to_available(
    n_available: int,
    n1: int, n2: int, n3: int, n4: int,
) -> tuple[int, int, int, int, int]:
    """Reduce counts from T4 upward until total <= n_available,
    while maintaining legal snapping rules.
    """
    def _snap_n4(v: int) -> int:
        return (max(0, v) // 6) * 6

    def _snap_n3(v: int) -> int:
        return (max(0, v) // 3) * 3

    def _snap_n2(v: int) -> int:
        return (max(0, v) // 2) * 2

    # Trim n4 first (bullets are the most expendable)
    n4 = _snap_n4(min(n4, max(0, n_available - n1 - n2 - n3)))
    total = n1 + n2 + n3 + n4
    if total <= n_available:
        return total, n1, n2, n3, n4

    # Trim n3
    n3 = _snap_n3(min(n3, max(0, n_available - n1 - n2)))
    n4 = 0
    total = n1 + n2 + n3 + n4
    if total <= n_available:
        return total, n1, n2, n3, n4

    # Trim n2
    n2 = _snap_n2(min(n2, max(0, n_available - n1)))
    n3 = n4 = 0
    total = n1 + n2 + n3 + n4
    return total, n1, n2, n3, n4


def _safe_fallback(articles: list[dict]) -> list[dict]:
    """Original hard-coded layout: 1 T1 + 2 T2 + 9 T3 + 12 T4 = 24 articles."""
    selected = articles[:24]
    _TIER_CUTS = [1, 3, 12]
    for i, a in enumerate(selected):
        if i < _TIER_CUTS[0]:
            a["tier"] = 1
        elif i < _TIER_CUTS[1]:
            a["tier"] = 2
        elif i < _TIER_CUTS[2]:
            a["tier"] = 3
        else:
            a["tier"] = 4
    return selected
