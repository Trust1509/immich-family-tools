"""
Face / person matching logic.

Strategy (in priority order):
1. Cosine similarity on face embeddings (if Immich exposes them)
2. Name similarity via Levenshtein distance
Only named people are automatic candidates. Unnamed people are matched manually.
"""
import logging
import hashlib
from typing import Optional
import numpy as np

from models.person import Person
from models.match import Match, MatchReason, MatchStatus, PersonRef

logger = logging.getLogger(__name__)


def _levenshtein(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            tmp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = tmp
    return dp[n]


def name_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Return 0-1 similarity between two names (None counts as empty string)."""
    na = (a or "").strip().lower()
    nb = (b or "").strip().lower()
    if not na and not nb:
        return 0.0  # both unnamed – no signal
    if not na or not nb:
        return 0.0  # one unnamed
    if na == nb:
        return 1.0
    max_len = max(len(na), len(nb))
    dist = _levenshtein(na, nb)
    return max(0.0, 1.0 - dist / max_len)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _match_id(person_a_id: str, person_b_id: str) -> str:
    key = "_".join(sorted([person_a_id, person_b_id]))
    return hashlib.md5(key.encode()).hexdigest()


def compute_matches(
    people: list[Person],
    embeddings: Optional[dict[str, list[float]]] = None,
    dismissed_ids: Optional[set[str]] = None,
    min_confidence: float = 0.25,
) -> list[Match]:
    """
    Compare every person in account A against every person in account B.
    Never compares persons within the same account.

    Parameters
    ----------
    people:         flat list of Person objects from all accounts
    embeddings:     {person_id: embedding_vector}  – optional
    dismissed_ids:  set of match IDs the user already dismissed
    min_confidence: drop matches below this threshold
    """
    dismissed_ids = dismissed_ids or set()

    # Group by account
    by_account: dict[str, list[Person]] = {}
    for p in people:
        by_account.setdefault(p.account_id, []).append(p)

    account_ids = list(by_account.keys())
    matches: list[Match] = []
    seen: set[str] = set()

    for i in range(len(account_ids)):
        for j in range(i + 1, len(account_ids)):
            acc_a = account_ids[i]
            acc_b = account_ids[j]
            for pa in by_account[acc_a]:
                for pb in by_account[acc_b]:
                    mid = _match_id(pa.id, pb.id)
                    if mid in seen:
                        continue
                    seen.add(mid)

                    confidence, reasons = _score_pair(pa, pb, embeddings)
                    if confidence < min_confidence:
                        continue

                    status = MatchStatus.dismissed if mid in dismissed_ids else MatchStatus.pending
                    matches.append(
                        Match(
                            id=mid,
                            person_a=PersonRef(
                                person_id=pa.id,
                                person_name=pa.name,
                                account_id=pa.account_id,
                                account_name=pa.account_name,
                                account_color=pa.account_color,
                            ),
                            person_b=PersonRef(
                                person_id=pb.id,
                                person_name=pb.name,
                                account_id=pb.account_id,
                                account_name=pb.account_name,
                                account_color=pb.account_color,
                            ),
                            confidence=round(confidence, 3),
                            reasons=reasons,
                            status=status,
                        )
                    )

    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches


def _score_pair(
    pa: Person,
    pb: Person,
    embeddings: Optional[dict[str, list[float]]],
) -> tuple[float, list[MatchReason]]:
    score = 0.0
    reasons: list[MatchReason] = []
    weights = {"embedding": 0.70, "name": 0.30}

    # 1. Embedding similarity
    if embeddings and pa.id in embeddings and pb.id in embeddings:
        cos = cosine_similarity(embeddings[pa.id], embeddings[pb.id])
        # Cosine for face embeddings is typically in [0.3, 1.0]
        # Normalize: treat 0.5 as 0%, 0.9 as 100%
        emb_score = max(0.0, (cos - 0.5) / 0.4)
        score += weights["embedding"] * emb_score
        if emb_score > 0:
            reasons.append(MatchReason.embedding_similarity)

    # 2. Name similarity
    name_sim = name_similarity(pa.name, pb.name)
    if name_sim > 0:
        score += weights["name"] * name_sim
        reasons.append(MatchReason.name_similarity)

    # Name-only matches deliberately top out at 75%, preventing bulk actions
    # from treating an identical name as biometric confirmation.
    if not (embeddings and pa.id in embeddings and pb.id in embeddings):
        score = 0.75 * name_sim

    return min(1.0, score), reasons
