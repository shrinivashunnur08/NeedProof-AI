"""14B.2: bounded privacy-minimized descriptive RFM segments + basket associations.

All rows are aggregate anonymous feature rows supplied by the caller; baskets are
unlinked product-code sets. No customer IDs, names, raw transaction details,
external I/O, model downloads, or persistence. Descriptive—not causal/predictive.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import log1p, sqrt
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CohortProfile14B2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recency_days: int = Field(ge=0, le=365)
    orders_90d: int = Field(ge=0, le=200)
    spend_minor_90d: int = Field(ge=0, le=200_000_000)


class CommerceInsightsInput14B2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profiles: list[CohortProfile14B2] = Field(min_length=24, max_length=120)
    baskets: list[list[str]] = Field(min_length=24, max_length=200)
    minimum_pair_orders: int = Field(default=3, ge=3, le=20)
    synthetic_demo: bool = False

    @model_validator(mode="after")
    def validate_baskets(self):
        import re
        unique = set()
        for basket in self.baskets:
            if not 2 <= len(basket) <= 8:
                raise ValueError("Each basket must contain 2–8 different product codes")
            if len(set(basket)) != len(basket):
                raise ValueError("Duplicate product in a basket is not allowed")
            for sku in basket:
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}", sku):
                    raise ValueError("Product identifiers must be short non-PII codes (letters/digits/._-)")
                unique.add(sku)
        if not 2 <= len(unique) <= 30:
            raise ValueError("Provide between 2 and 30 distinct product codes")
        return self


def _rank_vector(values: list[float]) -> list[float]:
    """Midranks make scale-invariant input and tie behavior explicit."""
    n = len(values)
    ordered = sorted(values)
    ranks: dict[float, float] = {}
    for v in set(values):
        # Bounded n<=120; O(n^2) avoids approximate rank instability.
        indices = [i for i, x in enumerate(ordered) if x == v]
        ranks[v] = (indices[0] + indices[-1]) / (n - 1) if n > 1 else 0.5
    return [ranks[x] for x in values]


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def _cluster(points: list[tuple[float, ...]], k: int) -> list[int] | None:
    """Deterministic farthest-first initialized k-means (stable under input reorder)."""
    unique = sorted(set(points))
    if len(unique) < k:
        return None
    overall = tuple(mean(x[i] for x in points) for i in range(3))
    centers = [min(unique, key=lambda x: (-_distance(x, overall), x))]
    for _ in range(k-1):
        centers.append(min((x for x in unique if x not in centers),
                           key=lambda x: (-min(_distance(x, c) for c in centers), x)))
    groups = [0] * len(points)
    for iteration in range(40):
        newgroups = [min(range(k), key=lambda j: (_distance(p, centers[j]), j)) for p in points]
        if iteration > 0 and groups == newgroups:
            break
        groups = newgroups
        if len(set(groups)) != k:
            return None
        centers = [tuple(mean(p[i] for p, g in zip(points, groups) if g == j)
                         for i in range(3)) for j in range(k)]
    if min(Counter(groups).values()) < 5:
        return None
    return groups


def _silhouette(points: list[tuple[float, ...]], labels: list[int]) -> float:
    n = len(points)
    groups: dict[int,list[int]] = {}
    for i,label in enumerate(labels):
        groups.setdefault(label,[]).append(i)
    distance = [[_distance(points[i], points[j]) for j in range(n)] for i in range(n)]
    scores = []
    for i,label in enumerate(labels):
        own = groups[label]
        if len(own) <= 1:
            scores.append(0.0)
            continue
        a = sum(distance[i][j] for j in own if j != i)/(len(own)-1)
        b = min(sum(distance[i][j] for j in group)/len(group)
                for other,group in groups.items() if other != label)
        scores.append((b-a)/max(a,b) if max(a,b)>0 else 0.0)
    return mean(scores)


def _profile_segments(profiles: list[CohortProfile14B2]) -> dict:
    n = len(profiles)
    # Lower recency is better; all axes are robust midranks, not income estimates.
    r = _rank_vector([-p.recency_days for p in profiles])
    f = _rank_vector([log1p(p.orders_90d) for p in profiles])
    m = _rank_vector([log1p(p.spend_minor_90d) for p in profiles])
    points = list(zip(r,f,m))
    options = []
    for k in (2,3,4):
        labels = _cluster(points,k)
        if labels is not None:
            score = _silhouette(points,labels)
            options.append((score - 0.025*(k-2),score,k,labels))
    best = max(options, key=lambda a:(a[0],-a[2])) if options else None
    if best is None or best[1] < 0.12:
        labels = [0] * n
        quality = None
    else:
        labels = best[3]
        quality = round(best[1],3)
    summaries=[]
    for label in sorted(set(labels)):
        group = [profiles[i] for i,v in enumerate(labels) if v==label]
        n_g = len(group)
        summaries.append({
            "_cluster":label,
            "count":n_g,
            "share_pct":round(100*n_g/n,1),
            "mean_recency_days":round(mean(p.recency_days for p in group),1),
            "mean_orders_90d":round(mean(p.orders_90d for p in group),2),
            "mean_spend_minor_90d":round(mean(p.spend_minor_90d for p in group)),
        })
    # Give ordinal cohort labels with stable high-spend-first ordering.
    summaries.sort(key=lambda x:(-x["mean_spend_minor_90d"],-x["mean_orders_90d"],x["mean_recency_days"]))
    for idx, group in enumerate(summaries):
        group["segment"] = f"Cohort {idx+1}"
        del group["_cluster"]
    return {
        "method":"DETERMINISTIC_RFM_MIDRANK_KMEANS_WITH_MINIMUM_COHORT_SIZE",
        "profile_count":n,
        "selected_k":len(summaries),
        "exploratory_silhouette":quality,
        "segments":summaries,
        "individual_assignments_disclosed":False,
        "min_reported_group_size":min(x["count"] for x in summaries),
        "interpretation":"Exploratory aggregate cohorts; no per-customer labels, targeting permissions, or demographic inference.",
    }


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    proportion=successes/total
    denom=1+z*z/total
    center=proportion+z*z/(2*total)
    width=z*sqrt(proportion*(1-proportion)/total + z*z/(4*total*total))
    return max(0.0,(center-width)/denom)


def _basket_rules(baskets: list[list[str]], threshold: int) -> dict:
    n=len(baskets)
    singles=Counter(x for b in baskets for x in b)
    pairs=Counter(pair for b in baskets for pair in combinations(sorted(b),2))
    rules=[]
    for (a,b), co in sorted(pairs.items()):
        if co < threshold or co/n < 0.05:
            continue
        for left,right in ((a,b),(b,a)):
            antecedent=singles[left]; consequent=singles[right]
            support=co/n
            confidence=co/antecedent
            baseline=consequent/n
            lift=confidence/baseline
            if lift < 1.10:
                continue
            rules.append({
                "antecedent_sku":left,"consequent_sku":right,
                "cooccurring_orders":co,
                "support_pct":round(100*support,2),
                "confidence_pct":round(100*confidence,2),
                "confidence_wilson95_lower_pct":round(100*_wilson_lower(co,antecedent),2),
                "lift":round(lift,3),
                "leverage":round(support-(antecedent/n)*(consequent/n),4),
                "association_only":True,
            })
    rules.sort(key=lambda r:(-r["cooccurring_orders"],-r["lift"],r["antecedent_sku"],r["consequent_sku"]))
    return {
        "method":"ORDER_PAIR_SUPPORT_CONFIDENCE_LIFT_WILSON_LOWER_BOUND",
        "basket_count":n,
        "distinct_product_codes":len(singles),
        "minimum_pair_orders":threshold,
        "rules":rules[:12],
        "eligible_rules_before_cap":len(rules),
        "interpretation":"Within-sample co-occurrence only; lift is not causal uplift or a validated cross-sell effect.",
    }


def evaluate_commerce_insights_14b2(payload: CommerceInsightsInput14B2) -> dict:
    return {
        "mode":"DESCRIPTIVE_COHORT_BASKET_INSIGHTS_14B2",
        "data_origin":"CLIENT_LABELED_SYNTHETIC_DEMO" if payload.synthetic_demo else "USER_SUPPLIED_UNVERIFIED_AGGREGATES",
        "segmentation":_profile_segments(payload.profiles),
        "basket_analysis":_basket_rules(payload.baskets,payload.minimum_pair_orders),
        "limitations":[
            "Input profiles are unlinked 90-day aggregate RFM features, not identifying customer records; never submit direct personal identifiers.",
            "Cohorts are exploratory descriptive clusters, not validated behavioral predictions or automatic targeting eligibility.",
            "Minimum displayed cohort size is five; no per-person segment assignments or individual inputs are returned.",
            "Market-basket rules describe sampled order co-occurrence, not causation or incremental promotional lift.",
            "Wilson bounds describe conditional item frequency and do not correct sampling bias or multiple comparisons.",
            "Sample selection, seasonality, returns and channel differences can materially alter findings.",
        ],
        "source_records_persisted":False,
        "direct_identifiers_accepted":False,
        "cloud_model_used":False,
        "purchase_allowed":False,
        "personalized_targeting_allowed":False,
        "independently_verified":False,
    }
