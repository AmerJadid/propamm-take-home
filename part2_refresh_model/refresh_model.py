"""Part 2 - optimal refresh interval T. Run: uv run python part2_refresh_model/refresh_model.py"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

GAS = 0.50  # $ per refresh                     given
VOLUME = 50e6  # $ per day                      given
FEE = 5e-4  # 5 bps, as a fraction              given
BLOCK = 0.75  # seconds                         given
CURRENT_BNB_PER_DAY = 7.2  # what they spend on gas today   given
BNB_USD = 627.0  # $ per BNB                    given
SIGMA = 0.80e-4  # 0.80 bps over 1 s as a fraction, scales as sqrt(t); measured, not given
DAY = 86_400.0

# The constant c in model.md. (2/3) averages sqrt(t) over the interval;
# sqrt(2/pi) turns a standard deviation into a mean absolute move.
SHAPE = (2 / 3) * math.sqrt(2 / math.pi)

# Their current operating point: 7.2 BNB/day at $627 buys this many $0.50 refreshes.
CURRENT_T = DAY / (CURRENT_BNB_PER_DAY * BNB_USD / GAS)

INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"


def gas_cost(T):
    return GAS / T * DAY


def staleness_cost(T, volume=VOLUME, sigma=SIGMA, phi=1.0):
    return SHAPE * phi * volume * sigma * math.sqrt(T)


def total_cost(T, volume=VOLUME, sigma=SIGMA, phi=1.0):
    return gas_cost(T) + staleness_cost(T, volume, sigma, phi)


def optimal_T(volume=VOLUME, sigma=SIGMA, phi=1.0):
    """T* = [2G / (c*phi*V*sigma)]^(2/3), from dC/dT = 0."""
    return (2 * GAS / (SHAPE * phi * (volume / DAY) * sigma)) ** (2 / 3)


def one_sigma_cap():
    """T at which a one-standard-deviation move, sigma*sqrt(T), equals the fee.

    Past this the constant-flow model breaks: the stale price attracts arbitrage
    rather than ordinary flow, so V is no longer a given."""
    return (FEE / SIGMA) ** 2


def penalty(u):
    """Cost at T = u*T*, relative to the best."""
    return 1 / (3 * u) + (2 / 3) * math.sqrt(u)


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=10.5, color=INK, pad=10, loc="left")
    ax.set_xlabel(xlabel, fontsize=9, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=9, color=MUTED)
    ax.tick_params(labelsize=8.5, colors=MUTED, length=3)
    ax.grid(True, color="#e8e7e3", linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d5d4cf")


def figure(path):
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.6), facecolor=SURFACE)
    T_star = optimal_T()

    Ts = [1.5 * 1.06**i for i in range(73)]
    for fn, colour, label in (
        (total_cost, BLUE, "total"),
        (gas_cost, ORANGE, "gas"),
        (staleness_cost, AQUA, "cost of a stale price"),
    ):
        ax1.plot(
            Ts, [fn(t) for t in Ts], color=colour, linewidth=2, solid_capstyle="round", label=label
        )
    ax1.axvline(T_star, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax1.plot(
        [T_star],
        [total_cost(T_star)],
        "o",
        color=BLUE,
        markersize=8,
        markeredgecolor=SURFACE,
        markeredgewidth=2,
        zorder=5,
    )
    ax1.annotate(
        f"T* = {T_star:.0f}s\n${total_cost(T_star):,.0f}/day",
        (T_star, total_cost(T_star)),
        textcoords="offset points",
        xytext=(12, -30),
        fontsize=9,
        color=INK,
    )
    leg = ax1.legend(
        loc="upper right",
        fontsize=9,
        frameon=False,
        handlelength=1.6,
        labelcolor=MUTED,
        borderpad=0,
    )
    leg.set_zorder(6)
    ax1.set_xscale("log")
    ax1.set_xlim(1.5, 100)
    ax1.set_ylim(0, 27_000)
    _style(ax1, "Gas falls, staleness rises", "refresh interval T (seconds, log)", "$ per day")

    vols = [10 ** (6 + i / 40) for i in range(121)]
    lo = [min(optimal_T(v, phi=1.0), one_sigma_cap()) for v in vols]
    hi = [min(optimal_T(v, phi=0.25), one_sigma_cap()) for v in vols]
    ax2.fill_between(vols, lo, hi, color=BLUE, alpha=0.13, linewidth=0)
    ax2.plot(vols, lo, color=BLUE, linewidth=2, solid_capstyle="round")
    ax2.axhline(one_sigma_cap(), color=ORANGE, linewidth=1.5, linestyle=(0, (4, 3)))
    ax2.axhline(BLOCK, color=MUTED, linewidth=1, linestyle=(0, (2, 3)))
    ax2.annotate(
        f"capped: a 1σ move would pass our fee ({one_sigma_cap():.0f}s)",
        (1.3e6, one_sigma_cap()),
        textcoords="offset points",
        xytext=(0, 7),
        fontsize=8.5,
        color=MUTED,
    )
    ax2.annotate(
        "one block (0.75s)",
        (1.3e6, BLOCK),
        textcoords="offset points",
        xytext=(0, 6),
        fontsize=8.5,
        color=MUTED,
    )
    ax2.annotate(
        "if only a quarter of\nflow is against us",
        (3e8, optimal_T(3e8, phi=0.25)),
        textcoords="offset points",
        xytext=(-20, 22),
        fontsize=8.5,
        color=MUTED,
    )
    ax2.plot(
        [VOLUME],
        [optimal_T()],
        "o",
        color=BLUE,
        markersize=8,
        markeredgecolor=SURFACE,
        markeredgewidth=2,
        zorder=5,
    )
    ax2.annotate(
        f"$50M/day\n{optimal_T():.0f}s",
        (VOLUME, optimal_T()),
        textcoords="offset points",
        xytext=(-12, -34),
        fontsize=9,
        color=INK,
    )
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlim(1e6, 1e9)
    ax2.set_ylim(0.4, 150)
    _style(
        ax2,
        "Ten times the volume needs 4.6x the refreshes, not ten",
        "daily volume ($, log)",
        "optimal T (seconds, log)",
    )

    us = [0.15 + i * 0.01 for i in range(486)]
    ax3.plot(
        us, [(penalty(u) - 1) * 100 for u in us], color=BLUE, linewidth=2, solid_capstyle="round"
    )
    ax3.axhline(0, color="#d5d4cf", linewidth=1)
    theirs = CURRENT_T / T_star
    ax3.plot(
        [theirs],
        [(penalty(theirs) - 1) * 100],
        "o",
        color=BLUE,
        markersize=8,
        markeredgecolor=SURFACE,
        markeredgewidth=2,
        zorder=5,
    )
    ax3.annotate(
        f"they run {CURRENT_T:.1f}s, only\n+{(penalty(theirs) - 1) * 100:.1f}% off the best",
        (theirs, (penalty(theirs) - 1) * 100),
        textcoords="offset points",
        xytext=(24, -36),
        fontsize=9,
        color=INK,
        arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.9},
    )
    for u, dx, dy in ((0.5, 8, 12), (2.0, 8, 6)):
        ax3.plot([u], [(penalty(u) - 1) * 100], "o", color=BLUE, markersize=5, zorder=5)
        ax3.annotate(
            f"half T*: +{(penalty(u) - 1) * 100:.0f}%"
            if u < 1
            else f"double T*: +{(penalty(u) - 1) * 100:.0f}%",
            (u, (penalty(u) - 1) * 100),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=8.5,
            color=MUTED,
        )
    ax3.set_xlim(0.15, 5)
    ax3.set_ylim(-16, 80)
    _style(
        ax3,
        "The optimum is flat: 2x off costs 11-14%",
        "T as a multiple of T*",
        "% worse than the best",
    )

    fig.tight_layout(pad=2.2)
    fig.savefig(path, dpi=170, facecolor=SURFACE)
    print(f"wrote {path}")


def main():
    T = optimal_T()
    print(
        f"sigma = {SIGMA * 1e4:.2f} bps over 1s (measured)   gas ${GAS:.2f}   "
        f"volume ${VOLUME / 1e6:g}M/day   fee {FEE * 1e4:g} bps\n"
    )
    print(f"  T*                {T:.1f} s   ({T / BLOCK:.0f} blocks, {DAY / T:,.0f} refreshes/day)")
    print(
        f"  cost at T*        ${total_cost(T):,.0f}/day  "
        f"(gas ${gas_cost(T):,.0f} + stale ${staleness_cost(T):,.0f})"
    )
    print(f"  revenue           ${VOLUME * FEE:,.0f}/day at {FEE * 1e4:g} bps")
    print(f"  1-sigma move at T* {SIGMA * math.sqrt(T) * 1e4:.2f} bps vs a {FEE * 1e4:g} bps fee")
    print(f"  they run          {CURRENT_T:.1f} s, {(penalty(CURRENT_T / T) - 1) * 100:.1f}% off")
    print(f"  feasible band     {BLOCK:g} s .. {one_sigma_cap():.0f} s   -> T* is interior\n")

    print(
        f"{'daily volume':>14}{'T* (s)':>9}{'blocks':>8}{'refresh/day':>13}{'gas/day':>10}"
        f"{'1-sigma':>10}"
    )
    print("-" * 64)
    for v in (5e6, 25e6, 50e6, 100e6, 500e6):
        t = min(optimal_T(v), one_sigma_cap())
        note = " *" if optimal_T(v) > one_sigma_cap() else ""
        print(
            f"{'$' + format(v / 1e6, ',.0f') + 'M':>14}{t:>9.1f}{t / BLOCK:>8.0f}"
            f"{DAY / t:>13,.0f}{'$' + format(DAY / t * GAS, ',.0f'):>10}"
            f"{SIGMA * math.sqrt(t) * 1e4:>7.1f}bps{note}"
        )
    print("  * capped: the unconstrained optimum would let a 1-sigma move exceed the fee\n")

    print(
        f"2-second Binance gap: a 1-sigma move is {SIGMA * math.sqrt(2) * 1e4:.2f} bps "
        f"against a {FEE * 1e4:g} bps fee, and shorter than T* itself -> not a staleness event."
    )
    print(f"It becomes one only past {one_sigma_cap():.0f} s.")
    figure(Path(__file__).with_name("refresh_model.png"))


if __name__ == "__main__":
    main()
