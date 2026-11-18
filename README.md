# Dip-Buy Mean Reversion — BTC 24h Race

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/ranstar04/btc-race-24h-20261118-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/ranstar04/btc-race-24h-20261118-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A deterministic dip-buy trading bot for the [make.fun](https://make.fun/r/dn9c31df)
**btc-race-24h-20261118-1444** bounty ("Race a BTC trading bot live for 24
hours", $250 prize pool). It trades Coinbase Wrapped BTC (cbBTC) against USDC,
minute by minute, on 1-minute on-chain prices from an Orca Whirlpool on
Solana. Paper money only — nothing is traded for real.

## Strategy

Single-file bot, `main.py` (Python 3.13, standard library only, integer math
only, no network, no clock, no randomness):

- **Flat:** buy ALL cash when the latest close is at least **1.8%** below the
  trailing **240-bar (4h)** high.
- **Long:** sell the whole position at **+1.5%** take-profit or **−1.5%**
  stop-loss from the entry fill.
- One position at a time, long only, no leverage, no shorts.

Why a 240-bar lookback: the dev window is a slow bleed (−2.8% over 24h) with
a narrow range, so a 360-bar trailing high is stale and buys falling knives.
A 240-bar high tracks the recent range instead. The chosen parameters sit
inside a broad profitable plateau — 16 of 20 neighbouring (dip, TP, SL)
combinations are also profitable on the dev window — so the edge is
structural, not a cherry-picked peak.

## Local results (dev window, kit grade-local)

| Metric | Value |
| --- | --- |
| Net PnL | **+$12.25** on $1,000 start |
| Trades | 3 filled orders (2 round trips; the 2nd closes at the end-of-window flatten) |
| Win rate | 1 of 2 round trips |
| Max drawdown | 0.64% |

Dev gate: net PnL above $0. Race guardrails: at least 1 trade, max
drawdown ≤ 25%.

## Run the grade locally

```sh
node cli/makefun.mjs grade-local --kit <kit-dir> --bot . --driver process
```

## Bounty

- Competition: https://make.fun/bounty/btc-race-24h-20261118-1444
- Entry deadline: 19 Nov 2026 03:44 WIB; race: 19 Nov 03:59 WIB – 20 Nov 03:59 WIB
- My referral: https://make.fun/r/dn9c31df
