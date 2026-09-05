"""Properties the design has to satisfy for the pool to be economically sound.

The brief only asks for the four cases, which are in test_pricing.py. Those
record what the model outputs; these check it is the right thing to output, and
are what would catch a sign error or a mis-derived boundary.

    test                                         what it checks
    -----------------------------------------    -------------------------------------
    buying never beats the oracle                never sell BNB below the price we
                                                 can rebuy it at
    selling never beats the oracle               mirror of the above
    round trip loses money                       no free money for arbitrageurs
    bid <= P <= ask, spread = the gap            matches what the brief says the
                                                 spread is
    alpha cannot change bid/ask                  documents the signature problem
    alpha = 1 is a plain xy=k pool               sanity anchor against Uniswap V2
    higher alpha gives more                      depth knob points the right way
    trading exactly the capacity hits 50/50      the continuity property
    trading past capacity splits phases          the stable phase has a real limit
    fee strictly reduces output                  the fee is actually applied
    curve cannot overpay the pool                the solvency guard
    invalid inputs rejected                      validation
"""

from itertools import pairwise

import pytest

from part1_pricing.pricing import get_bid_ask, get_quote, stable_phase_capacity

P = 627.0
BALANCED, X_HEAVY, Y_HEAVY = (100.0, 62_700.0), (120.0, 50_000.0), (80.0, 75_000.0)
POOLS = [BALANCED, X_HEAVY, Y_HEAVY]


@pytest.mark.parametrize("reserves", POOLS)
@pytest.mark.parametrize("size", [1.0, 500.0, 20_000.0])
def test_buying_wbnb_never_beats_the_oracle(reserves, size):
    """Otherwise the pool sells inventory below the price it can rebuy at."""
    _out, price, _fee = get_quote(*reserves, P, 1.02, 0.0, size, False)
    assert price >= P - 1e-9


@pytest.mark.parametrize("reserves", POOLS)
@pytest.mark.parametrize("size", [0.01, 5.0, 40.0])
def test_selling_wbnb_never_beats_the_oracle(reserves, size):
    """40 BNB is past the Y-heavy pool's 19.8 BNB capacity, so this exercises
    the sell side across both phases rather than only the flat one."""
    _out, price, _fee = get_quote(*reserves, P, 1.02, 0.0, size, True)
    assert price <= P + 1e-9


@pytest.mark.parametrize("reserves", POOLS)
def test_round_trip_loses_money(reserves):
    """Buy then immediately sell back. Must lose even with no fee, or the pool
    is printing free money for arbitrageurs."""
    x, y = reserves
    bought, _price, _fee = get_quote(x, y, P, 1.02, 0.0, 1_000.0, False)
    back, _price, _fee = get_quote(x - bought, y + 1_000.0, P, 1.02, 0.0, bought, True)
    assert back < 1_000.0


@pytest.mark.parametrize("reserves", POOLS)
def test_bid_ask_bracket_the_oracle_and_spread_is_the_gap(reserves):
    """The brief says the spread comes from the gap between P and cpPrice."""
    x, y = reserves
    bid, ask = get_bid_ask(x, y, P, 1.02)
    assert bid <= P <= ask
    assert ask - bid == pytest.approx(abs(P - y / x))


def test_alpha_cannot_change_bid_ask():
    """alpha scales both reserves, so it cancels out of the price ratio. This
    is why the required get_bid_ask signature cannot use its alpha argument."""
    quotes = {get_bid_ask(*X_HEAVY, P, a) for a in (1.0, 1.02, 100.0, 5_000.0)}
    assert len(quotes) == 1


def test_alpha_one_reduces_to_plain_constant_product():
    x, y, size = *BALANCED, 500.0
    out, _price, _fee = get_quote(x, y, P, 1.0, 0.0, size, False)
    assert out == pytest.approx(x * size / (y + size))


def test_higher_alpha_gives_the_trader_more():
    outs = [get_quote(*BALANCED, P, a, 0.0, 20_000.0, False)[0] for a in (1.0, 1.02, 100.0)]
    assert all(a < b for a, b in pairwise(outs))


@pytest.mark.parametrize("reserves", POOLS)
@pytest.mark.parametrize("swap_x_to_y", [True, False])
def test_trading_exactly_the_capacity_lands_the_pool_on_5050(reserves, swap_x_to_y):
    """This continuity property is why only the rebalancing portion gets the
    flat price: the curve then starts at exactly P, with no jump between phases."""
    x, y = reserves
    capacity = stable_phase_capacity(x, y, P, swap_x_to_y)
    if capacity <= 0:
        pytest.skip("this direction does not rebalance this pool")
    out, price, _fee = get_quote(x, y, P, 1.02, 0.0, capacity, swap_x_to_y)
    assert price == pytest.approx(P)
    x2, y2 = (x + capacity, y - out) if swap_x_to_y else (x - out, y + capacity)
    assert y2 / x2 == pytest.approx(P)


def test_a_trade_past_the_capacity_splits_across_both_phases():
    """Beyond the flat slab the price must degrade, otherwise the whole trade
    clears at P and the pool can be emptied at a fixed price."""
    capacity = stable_phase_capacity(*X_HEAVY, P, False)
    _out, price, _fee = get_quote(*X_HEAVY, P, 1.02, 0.0, capacity * 4, False)
    assert price > P


def test_fee_strictly_reduces_the_output():
    """Strict, not merely non-increasing: a fee that is charged but never
    applied leaves every output identical, which sorted() would accept."""
    outs = [get_quote(*BALANCED, P, 1.02, f, 500.0, False)[0] for f in (0.0, 5.0, 100.0)]
    assert all(a > b for a, b in pairwise(outs))


def test_curve_cannot_pay_out_more_than_the_pool_holds():
    """Virtual reserves are not real tokens, so the payout tends to
    alpha * reserve_out. A plain xy=k pool (alpha = 1) is safe."""
    with pytest.raises(ValueError, match="exceeds the real reserve"):
        get_quote(*BALANCED, P, 1.02, 0.0, 4_000_000.0, False)
    out, _price, _fee = get_quote(*BALANCED, P, 1.0, 0.0, 4_000_000.0, False)
    assert out < 100.0
    # Only floating-point rounding can make alpha = 1 hit the guard; it must
    # still be a clean rejection, not a division by zero in the message.
    with pytest.raises(ValueError, match="exceeds the real reserve"):
        get_quote(*BALANCED, P, 1.0, 0.0, 1e300, False)


@pytest.mark.parametrize(
    "args",
    [
        (0.0, 62_700.0, P, 1.02, 0.0, 1.0),
        (100.0, 62_700.0, 0.0, 1.02, 0.0, 1.0),
        (100.0, 62_700.0, P, 0.98, 0.0, 1.0),
        (100.0, 62_700.0, P, 1.02, -1.0, 1.0),
        (100.0, 62_700.0, P, 1.02, 10_001.0, 1.0),
        (100.0, 62_700.0, P, 1.02, 0.0, -1.0),
        (float("nan"), 62_700.0, P, 1.02, 0.0, 1.0),
        (100.0, 62_700.0, P, 1.02, 0.0, float("nan")),
    ],
)
def test_invalid_inputs_are_rejected(args):
    with pytest.raises(ValueError):
        get_quote(*args, False)
