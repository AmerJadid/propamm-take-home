# PropAMM Take-Home

The covering email asks for any two of the four parts. This answers **Part 1**
and **Part 2**. Parts 3 and 4 are not attempted.

```
part1_pricing/          quote engine + test cases A-D
part2_refresh_model/    optimal refresh interval, derivation and chart
```

## Run it

```bash
make install   # install dependencies
make part1     # prints the A-D results
make part2     # prints the refresh model and writes its chart
make test      # run the tests
```

Or without `make`: `uv sync`, then `uv run python part1_pricing/pricing.py`.

## Part 1 — how it works

Every trade is split in two:

1. **Stable phase.** The part of the trade that moves the pool toward a 50/50
   split by value trades at the flat oracle price `P`, with no slippage. There
   is a hard limit on how much this can be — the amount that lands the pool
   exactly on 50/50, which works out to half the pool's imbalance.
2. **Curve phase.** Anything left over trades on the `xy=k` curve, where the
   price gets worse the more you take.

Bid and ask fall out of the same rule. The pool quotes the fair price on
whichever side helps it and a deliberately bad price on the side that hurts,
so the spread is exactly the gap between `P` and the price implied by the
reserves — which is what the brief describes.

### Results

`make part1` prints this table. All four cases send 500 USDT and receive WBNB
at `P = 627`, with a 5 bps fee on the input.

| Case | Reserves (WBNB / USDT) | alpha | amount_out (WBNB) | effective price | fee (USDT) | stable / curve (USDT) | bid | ask |
|:---:|---|:---:|---|---|---|---|---|---|
| A | 100 / 62,700 | 1.02 | 0.79086942 | 632.2156 | 0.25 | 0 / 499.75 | 627.00 | 627.00 |
| B | 80 / 75,000 | 1.02 | 0.52960691 | 944.0964 | 0.25 | 0 / 499.75 | 627.00 | 937.50 |
| C | 120 / 50,000 | 1.02 | 0.79704944 | 627.3137 | 0.25 | 499.75 / 0 | 416.67 | 627.00 |
| D | 100 / 62,700 | 1.05 | 0.79104466 | 632.0756 | 0.25 | 0 / 499.75 | 627.00 | 627.00 |

Only case C reaches the stable phase: it is the one trade that helps the pool,
so it clears at `P` and pays only the fee. A, B and D push the pool off balance,
so they are pure curve. B is short of WBNB and gives up more only at a steep
markup, hence 944. A and D differ only in `alpha`, and 1.05 buys the trader
about 2 bps more than 1.02.

## Assumptions

- `reserve_x` is WBNB, `reserve_y` is USDT, and `price_P` is USDT per WBNB.
- "50/50" means the two sides are worth the same at `P`, i.e. `x * P == y`.
- Only the portion of a trade that reaches 50/50 gets the flat price; the rest
  goes on the curve. **This does not change any of the four test cases** — see
  the ambiguities below.
- The curve for the remainder is built on the reserves left after the stable
  leg, so its marginal price starts at exactly `P`. Built on the pre-trade
  reserves instead, case C's curve would open at about 622, below `P`, handing
  the trader a better price after the flat leg than during it.
- The fee comes off the token you send in, the convention Uniswap and
  PancakeSwap use, so `fee_charged` is in USDT for all four cases.
- The test table gives no fee, so the results use **5 bps** — the spread quoted
  in Part 2, and a real PancakeSwap fee tier for this pair. It is a parameter of
  `get_quote`, so any other rate can be passed in.
- `effective_price` is always USDT per WBNB, in both directions, and includes
  the fee. It is the blended average for the whole trade.
- Plain floating point. Real contracts would use integer arithmetic with
  rounding set against the trader.

## What the brief left unclear, and what we did

**The stable phase has no stated size limit.** It says trades that rebalance the
pool trade at `P`, but not whether that means the whole trade or only the part
that reaches 50/50. We take the second reading, because the task says the curve
prices "the remainder", and because it joins the two phases smoothly — the
stable phase ends exactly at `P`, so the curve starts there with no jump. It
makes no difference to cases A–D either way.

**No fee is given in the test table.** We use 5 bps, for the reason above.

**`get_bid_ask` takes `alpha`, but `alpha` cannot affect it.** It scales both
reserves equally, so it cancels out of the price. A test checks that `alpha`
values from 1 to 5,000 all return the same answer. `alpha` only matters once a
trade has a size, which this function has no argument for. For the same reason
the bid and ask are touch prices before the fee.

**`alpha` at 1.02 adds 2% of extra depth.** That is a small effect next to the
20–4,000× amplification typical of concentrated pools, and it shows up in the
results: a 500 USDT trade pays 78 bps of curve slippage (83 bps with the fee)
against a 5 bps target spread, and the 1.02 vs 1.05 comparison in cases A and D
moves the price by only about 2 bps. We implement it exactly as specified; it
would be worth confirming the intended magnitude.

**The curve can promise more than the pool holds.** Payouts approach
`alpha × reserves`, which is more than the real balance, so a large enough trade
would leave the pool short. A plain `xy=k` pool cannot do this. We reject such
quotes rather than quietly capping them.

## Part 2 — Optimal Refresh Frequency

Derivation, constraints and chart in
[`part2_refresh_model/model.md`](part2_refresh_model/model.md). The brief asks
for a notebook or PDF; this is a markdown write-up plus the script that
generates every number and the chart, so it renders on GitHub without a kernel
and `make part2` reproduces it.

Refreshing often costs gas; refreshing rarely lets the on-chain price drift, and
people trade against it at the wrong price. Minimising the sum of the two:

```
C(T) = G/T + c·V·σ·√T        →        T* = [ 2G / (c·V·σ) ] ^ (2/3)
```

**T\* ≈ 12 seconds** at the stated $50M/day, about 16 BSC blocks. They currently
refresh every 9.6 s, which is within 1.2% of the cheapest possible. `T*` scales
as `volume^(-2/3)`, so ten times the volume needs 4.6 times the refreshes, not
ten.

**The 2-second Binance silence is not a staleness event.** The price moves about
1.1 bps in two seconds against a 5 bps fee, so there is nothing to lose. It only
becomes one past about 39 seconds.

### Assumptions

- **Volatility is the one input the brief does not give.** We measured it from
  Binance's public price history for BNBUSDT (`make sigma` re-runs the
  measurement) and use **0.80 bps over one second** — meaning a
  one-standard-deviation move is about 0.8 bps in a second and `√T` times that
  over `T` seconds, so about 45% a year. Measured across windows from 17 minutes to
  2.7 years it ranges 0.67–1.28 bps (37%–72% a year); the one-second figure is
  the high end and is inflated by bid-ask bounce. Using 0.80 across that whole
  range costs at most 2.5%, because `T*` moves as `σ^(-2/3)` and the optimum is
  flat, so the two effects nearly cancel.
- We assume all flow is trading against us — the conservative reading, and
  defensible because routers send us the wrong side whenever our price is off.
  If only a quarter of it is, the answer moves to about 30 seconds.
- Drift is dropped from the price process. Over these seconds it is 0.05% of the
  noise; it would not be droppable over a day.
- Gas is taken as the stated $0.50 per refresh. It cross-checks: 7.2 BNB/day is
  about $4,514, which at $0.50 each is one refresh every 9.6 seconds.
