from functools import lru_cache
from itertools import combinations
from server.matching import can_complete, valid_candidates


@lru_cache(maxsize=None)
def oracle(givers, recipients):
    if not givers:
        return True
    giver = givers[0]
    return any(r != giver and oracle(givers[1:], tuple(x for x in recipients if x != r)) for r in recipients)


def test_all_eight_person_subproblems_against_independent_exhaustive_oracle():
    # Every possible equally sized subset of remaining givers and recipients,
    # including states a naive algorithm could leave impossible.
    people = tuple(range(8))
    cases = 0
    for size in range(9):
        for givers in combinations(people, size):
            for recipients in combinations(people, size):
                feasible = oracle(givers, recipients)
                assert can_complete(givers, recipients) == feasible
                for giver in givers:
                    expected = [r for r in recipients if r != giver and oracle(tuple(g for g in givers if g != giver), tuple(x for x in recipients if x != r))]
                    assert valid_candidates(giver, givers, recipients) == expected
                    if feasible:
                        assert expected
                cases += 1
    assert cases == 12870


def test_dead_end_candidate_is_excluded():
    # Giver 1 -> 3 would leave giver 2 with only themselves.
    assert valid_candidates(1, [1, 2], [2, 3]) == [2]
    assert valid_candidates(1, [1], [1]) == []
