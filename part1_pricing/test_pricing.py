"""The four test cases from the brief, with their results.

These are recorded outputs, so they pin the numbers and make any change
visible. They do not by themselves show the model is right - the properties
that do are in test_properties.py.
"""

import pytest

from part1_pricing.pricing import get_bid_ask, get_quote, stable_phase_capacity

P, FEE_BPS, AMOUNT_IN = 627.0, 5.0, 500.0

# case, reserve_x, reserve_y, alpha, amount_out, effective_price, bid, ask, reaches_stable
CASES = [
    ("A", 100.0, 62_700.0, 1.02, 0.79086942, 632.2156, 627.00, 627.00, False),
    ("B", 80.0, 75_000.0, 1.02, 0.52960691, 944.0964, 627.00, 937.50, False),
    ("C", 120.0, 50_000.0, 1.02, 0.79704944, 627.3137, 416.67, 627.00, True),
    ("D", 100.0, 62_700.0, 1.05, 0.79104466, 632.0756, 627.00, 627.00, False),
]


@pytest.mark.parametrize("case,x,y,alpha,out,price,bid,ask,stable", CASES)
def test_case(case, x, y, alpha, out, price, bid, ask, stable):
    amount_out, effective_price, fee_charged = get_quote(
        x, y, P, alpha, FEE_BPS, AMOUNT_IN, swap_x_to_y=False
    )
    assert amount_out == pytest.approx(out, abs=5e-9)
    assert effective_price == pytest.approx(price, abs=5e-5)
    assert fee_charged == pytest.approx(AMOUNT_IN * FEE_BPS / 10_000)
    assert get_bid_ask(x, y, P, alpha) == pytest.approx((bid, ask), abs=5e-3)

    # Only a trade that rebalances the pool reaches the flat-price phase. A
    # stable leg in A, B or D would mean the balance test has the wrong sign.
    capacity = stable_phase_capacity(x, y, P, swap_x_to_y=False)
    assert (capacity > 0) is stable


def test_case_c_is_the_only_one_that_rebalances_the_pool():
    """C's 500 USDT sits inside a 12,620 USDT capacity, so it clears wholly at
    the oracle price; the other three are entirely on the curve."""
    assert stable_phase_capacity(120.0, 50_000.0, P, False) == pytest.approx(12_620.0)
    _out, price, _fee = get_quote(120.0, 50_000.0, P, 1.02, 0.0, AMOUNT_IN, False)
    assert price == pytest.approx(P)
