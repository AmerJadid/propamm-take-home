"""Checks that the closed-form answer in refresh_model.py is the minimum it claims to be."""

import pytest

from part2_refresh_model.refresh_model import (
    BLOCK,
    CURRENT_T,
    gas_cost,
    one_sigma_cap,
    optimal_T,
    penalty,
    staleness_cost,
    total_cost,
)


def test_closed_form_matches_a_brute_force_minimum():
    grid = [i / 100 for i in range(100, 10_000)]  # 1 s to 100 s in 0.01 s steps
    numeric = min(grid, key=total_cost)
    assert optimal_T() == pytest.approx(numeric, abs=0.01)


def test_stale_cost_is_twice_gas_at_the_optimum():
    """Falls out of the first-order condition, at any volume."""
    for volume in (5e6, 50e6, 500e6):
        T = optimal_T(volume)
        assert staleness_cost(T, volume) == pytest.approx(2 * gas_cost(T))


def test_optimum_scales_as_volume_to_the_minus_two_thirds():
    assert optimal_T(10 * 50e6) == pytest.approx(optimal_T(50e6) * 10 ** (-2 / 3))


def test_penalty_is_one_at_the_optimum_and_worse_either_side():
    assert penalty(1.0) == pytest.approx(1.0)
    assert penalty(0.5) > 1.0 and penalty(2.0) > 1.0
    assert penalty(0.5) == pytest.approx(total_cost(0.5 * optimal_T()) / total_cost(optimal_T()))


def test_headline_numbers():
    """The figures quoted in model.md and README.md."""
    T = optimal_T()
    assert 11.5 < T < 12.5
    assert total_cost(T) == pytest.approx(10_970, abs=5)
    assert one_sigma_cap() == pytest.approx(39.06, abs=0.01)
    assert CURRENT_T == pytest.approx(9.57, abs=0.01)
    assert BLOCK < T < one_sigma_cap()
