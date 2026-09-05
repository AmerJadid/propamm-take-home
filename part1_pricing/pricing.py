"""Two-phase PropAMM pricing for WBNB/USDT.

The part of a trade that moves the pool toward a 50/50 split by value clears at
the flat oracle price; the remainder prices on a concentrated xy=k curve.
Assumptions are in README.md.
"""

from __future__ import annotations

import math

BPS = 10_000.0


def get_quote(
    reserve_x: float,
    reserve_y: float,
    price_P: float,
    alpha: float,
    fee_bps: float,
    amount_in: float,
    swap_x_to_y: bool,
) -> tuple[float, float, float]:
    """Quote a swap. Returns (amount_out, effective_price, fee_charged).

    reserve_x is WBNB, reserve_y is USDT, price_P is USDT per WBNB.
    swap_x_to_y sends WBNB and receives USDT; False is the reverse.
    effective_price is USDT per WBNB in both directions and includes the fee.
    fee_charged is in whichever token was sent in.
    """
    _validate(reserve_x, reserve_y, price_P, alpha)
    if not 0 <= fee_bps <= BPS:
        raise ValueError("fee_bps must be between 0 and 10,000")
    if not amount_in >= 0:
        raise ValueError("amount_in must be non-negative")

    fee_charged = amount_in * fee_bps / BPS
    net_in = amount_in - fee_charged

    capacity = stable_phase_capacity(reserve_x, reserve_y, price_P, swap_x_to_y)
    stable_in = min(net_in, capacity)
    stable_out = stable_in * price_P if swap_x_to_y else stable_in / price_P

    # Build the curve on the reserves left after the stable leg. Once that leg
    # lands the pool on 50/50, y/x equals price_P, so the curve starts at
    # exactly P and the two phases join without a jump in price.
    if swap_x_to_y:
        res_in, res_out = reserve_x + stable_in, reserve_y - stable_out
    else:
        res_in, res_out = reserve_y + stable_in, reserve_x - stable_out
    curve_out = _curve_out(res_in, res_out, alpha, net_in - stable_in)

    amount_out = stable_out + curve_out
    if amount_out <= 0:
        return 0.0, float("nan"), fee_charged
    effective_price = amount_out / amount_in if swap_x_to_y else amount_in / amount_out
    return amount_out, effective_price, fee_charged


def get_bid_ask(
    reserve_x: float, reserve_y: float, price_P: float, alpha: float
) -> tuple[float, float]:
    """Current bid and ask at the touch, both in USDT per WBNB, before fees.

    Buying WBNB only rebalances an X-heavy pool, so the ask is max(P, cpPrice);
    selling only rebalances a Y-heavy one, so the bid is min(P, cpPrice). The
    spread is therefore exactly |P - cpPrice|, as the brief describes.

    alpha is accepted to match the required signature but cannot change the
    answer: it scales both reserves, so it cancels out of (y+vy)/(x+vx).
    """
    _validate(reserve_x, reserve_y, price_P, alpha)
    cp_price = reserve_y / reserve_x
    return min(price_P, cp_price), max(price_P, cp_price)


def stable_phase_capacity(
    reserve_x: float, reserve_y: float, price_P: float, swap_x_to_y: bool
) -> float:
    """Input that clears at the flat price before the pool reaches 50/50.

    Zero when the trade direction moves the pool further off balance. Solving
    (x - dy/P) * P == y + dy gives dy = (x*P - y) / 2 for Y->X, and
    symmetrically dx = (y - x*P) / (2*P) for X->Y.
    """
    _validate(reserve_x, reserve_y, price_P)
    gap = reserve_x * price_P - reserve_y
    return max(0.0, -gap / (2.0 * price_P)) if swap_x_to_y else max(0.0, gap / 2.0)


def _curve_out(reserve_in: float, reserve_out: float, alpha: float, amount_in: float) -> float:
    """Output from (x + vx)(y + vy) = L^2 where each v = reserve * (alpha - 1).

    Effective reserves are alpha * reserve, so the payout reduces to
    alpha*Ro * a / (alpha*Ri + a). Because the virtual reserves are not real
    tokens, that tends to alpha * reserve_out as the input grows, which is more
    than the pool holds; we reject rather than quote a fill we cannot settle.
    """
    if amount_in <= 0:
        return 0.0
    out = alpha * reserve_out * amount_in / (alpha * reserve_in + amount_in)
    if out >= reserve_out:
        limit = alpha * reserve_in / (alpha - 1.0) if alpha > 1.0 else math.inf
        raise ValueError(
            f"payout {out:,.4f} exceeds the real reserve of {reserve_out:,.4f}; "
            f"the most this curve can take is {limit:,.2f}"
        )
    return out


def _validate(reserve_x: float, reserve_y: float, price_P: float, alpha: float = 1.0) -> None:
    # Written as "not (ok)" so that NaN, which fails every comparison, is rejected too.
    if not (reserve_x > 0 and reserve_y > 0):
        raise ValueError("reserves must be positive")
    if not price_P > 0:
        raise ValueError("price_P must be positive")
    if not alpha >= 1:
        raise ValueError("alpha must be >= 1; below 1 implies negative virtual reserves")


if __name__ == "__main__":
    P, FEE_BPS, AMOUNT_IN = 627.0, 5.0, 500.0
    # label, reserve_x (WBNB), reserve_y (USDT), alpha
    cases = [
        ("A", 100.0, 62_700.0, 1.02),
        ("B", 80.0, 75_000.0, 1.02),
        ("C", 120.0, 50_000.0, 1.02),
        ("D", 100.0, 62_700.0, 1.05),
    ]
    print(f"WBNB/USDT, oracle P = {P:g} USDT per WBNB, fee = {FEE_BPS:g} bps on the input.")
    print(f"All four cases send {AMOUNT_IN:,.0f} USDT and receive WBNB.\n")
    header = (
        f"{'case':<5}{'reserves':>22}{'alpha':>7}{'amount_out (WBNB)':>20}{'eff price':>12}"
        f"{'fee':>7}{'stable / curve (USDT)':>24}{'bid':>10}{'ask':>10}"
    )
    print(header, "-" * len(header), sep="\n")
    for label, x, y, a in cases:
        out, price, fee = get_quote(x, y, P, a, FEE_BPS, AMOUNT_IN, False)
        stable = min(AMOUNT_IN - fee, stable_phase_capacity(x, y, P, False))
        bid, ask = get_bid_ask(x, y, P, a)
        print(
            f"{label:<5}{f'{x:g} / {y:,.0f}':>22}{a:>7.2f}{out:>20.8f}{price:>12,.4f}"
            f"{fee:>7,.2f}{f'{stable:,.2f} / {AMOUNT_IN - fee - stable:,.2f}':>24}"
            f"{bid:>10,.2f}{ask:>10,.2f}"
        )
    print(
        "\nOnly C rebalances the pool, so only C reaches the stable phase, and its\n"
        "499.75 USDT net of fee fits inside a 12,620 USDT capacity - it clears wholly at P.\n"
        "A, B and D push the pool off balance, so they are pure curve.\n"
        "A and D are balanced, so cpPrice equals P and the quoted spread is zero."
    )
