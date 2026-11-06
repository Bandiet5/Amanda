"""Exact bipartite feasibility; no random choices on the client."""
from functools import lru_cache


@lru_cache(maxsize=32768)
def can_complete(givers: tuple[int, ...], recipients: tuple[int, ...]) -> bool:
    """Find an augmenting-path matching, excluding every self-edge."""
    if len(givers) != len(recipients):
        return False
    matched: dict[int, int] = {}

    def augment(giver, seen):
        for recipient in recipients:
            if recipient == giver or recipient in seen:
                continue
            seen.add(recipient)
            if recipient not in matched or augment(matched[recipient], seen):
                matched[recipient] = giver
                return True
        return False

    return all(augment(giver, set()) for giver in givers)


def valid_candidates(giver: int, givers, recipients) -> list[int]:
    remaining_givers = tuple(sorted(g for g in givers if g != giver))
    return [r for r in recipients if r != giver and can_complete(
        remaining_givers, tuple(sorted(other for other in recipients if other != r)))]
