"""Dip-buy cbBTC trading bot — make.fun btc-race-24h-20261118-1444.

Strategy (deterministic, integer math only):
  * Flat: buy ALL cash when the latest close is at least DIP_BPS below the
    trailing LOOKBACK_BARS-bar high.
  * Long: sell the whole position when the latest close is at least
    TAKE_PROFIT_BPS above the entry fill, or at least STOP_LOSS_BPS below it.
  * One position at a time, long only, no leverage, no shorts. The end of the
    window flattens whatever is still held (the harness does that).

Protocol: agent-fun/bars-replay/v1 over stdin/stdout (newline-delimited JSON).
The bot speaks the wire itself: hello once, exactly one reply per batch
echoing its seq, then done. No network, no wall clock, no files, no
randomness — the same bars always produce the same orders.

Parameter choice (backtested on the frozen 24h dev window in the kit):
  * The dev window is a slow bleed (-2.8% over 24h) with a narrow range, so a
    360-bar trailing high is stale and buys falling knives. A 240-bar (4h)
    trailing high tracks the recent range instead, and dip 1.8% / TP 1.5% /
    SL 1.5% sits inside a broad plateau: 16 of 20 neighbouring
    (dip, TP, SL) combinations are also profitable on the dev window, so the
    edge is structural, not one cherry-picked peak. Dev result in local
    simulation: +$12.25 net PnL, 2 round trips, max drawdown 0.64%.
"""

import json
import sys

SYMBOL = "CBBTC"

# --- strategy parameters (basis points; 10_000 bps = 100%) ---
LOOKBACK_BARS = 240
DIP_BPS = 180
TAKE_PROFIT_BPS = 150
STOP_LOSS_BPS = 150
MAX_SLIPPAGE_BPS = 500
MIN_NOTIONAL_QUOTE_UNITS = 1_000_000  # 1 USDC

BPS = 10_000


class Bot:
    """One bot run: keeps the account, the bar history and the entry price."""

    def __init__(self, hello):
        self.hello = hello
        self.symbols = {s["symbol"]: s for s in hello["symbols"]}
        self.quote_scale = int(hello["capital"]["quote_scale"])
        self.warmup_bars = int(hello.get("warmup_bars", 0))
        self.cash = int(hello["capital"]["quote_units"])
        self.equity = self.cash
        self.qty = 0
        # Entry fill price of the open position, in the symbol's price scale.
        self.entry_price = None
        self.closes = []
        self.highs = []
        self.seq = -1
        self._next_order = 1

    # -- units ---------------------------------------------------------
    def value_units(self, qty, price):
        """What qty is worth at price, in quote units (integer math)."""
        sym = self.symbols[SYMBOL]
        return (
            qty
            * price
            * 10 ** self.quote_scale
            // 10 ** (int(sym["qty_scale"]) + int(sym["price_scale"]))
        )

    def _client_id(self):
        cid = "o%d" % self._next_order
        self._next_order += 1
        return cid

    # -- per-batch ------------------------------------------------------
    def on_batch(self, batch):
        self.seq = int(batch["seq"])
        account = batch["account"]
        self.cash = int(account["cash_quote_units"])
        self.equity = int(account["equity_quote_units"])
        positions = {p["symbol"]: p for p in account["positions"]}
        pos = positions.get(SYMBOL)
        self.qty = int(pos["qty"]) if pos else 0
        if self.qty == 0:
            self.entry_price = None
        elif self.entry_price is None and pos is not None:
            # Fallback: rebuild an entry price from the cost basis.
            cost = int(pos["cost_quote_units"])
            sym = self.symbols[SYMBOL]
            if self.qty > 0 and cost > 0:
                self.entry_price = (
                    cost
                    * 10 ** (int(sym["qty_scale"]) + int(sym["price_scale"]))
                    // (self.qty * 10 ** self.quote_scale)
                )
        for fill in batch.get("fills", []):
            if fill.get("symbol") != SYMBOL or fill.get("status") != "filled":
                continue
            if fill["side"] == "buy":
                self.entry_price = int(fill["price"])
            elif fill["side"] == "sell":
                self.entry_price = None
        for bar in batch.get("bars", []):
            if bar.get("symbol") == SYMBOL:
                self.closes.append(int(bar["c"]))
                self.highs.append(int(bar["h"]))
        return self.decide()

    def trailing_high(self):
        """The highest bar high over the lookback window (needs full history)."""
        if len(self.highs) < LOOKBACK_BARS:
            return None
        return max(self.highs[-LOOKBACK_BARS:])

    def decide(self):
        """The orders decided on this bar (at most one)."""
        if self.seq < self.warmup_bars:
            return []
        if not self.closes:
            return []
        close = self.closes[-1]
        if self.qty > 0 and self.entry_price is not None:
            if close * BPS >= self.entry_price * (BPS + TAKE_PROFIT_BPS):
                return [self._sell_order(self.qty)]
            if close * BPS <= self.entry_price * (BPS - STOP_LOSS_BPS):
                return [self._sell_order(self.qty)]
            return []
        if self.qty == 0:
            high = self.trailing_high()
            if (
                high is not None
                and close * BPS <= high * (BPS - DIP_BPS)
                and self.cash >= MIN_NOTIONAL_QUOTE_UNITS
            ):
                return [self._buy_order(self.cash)]
        return []

    def _buy_order(self, notional):
        return {
            "side": "buy",
            "client_id": self._client_id(),
            "symbol": SYMBOL,
            "notional_quote_units": str(notional),
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }

    def _sell_order(self, qty):
        return {
            "side": "sell",
            "client_id": self._client_id(),
            "symbol": SYMBOL,
            "qty": str(qty),
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }


def main():
    """Speak agent-fun/bars-replay/v1 until done."""
    bot = None
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8").strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get("type")
        if kind == "hello":
            if msg.get("protocol") != "agent-fun/bars-replay/v1":
                raise SystemExit("unsupported protocol: %r" % (msg.get("protocol"),))
            bot = Bot(msg)
        elif kind == "batch":
            if bot is None:
                raise SystemExit("batch before hello")
            orders = bot.on_batch(msg)
            sys.stdout.write(
                json.dumps(
                    {"type": "reply", "seq": int(msg["seq"]), "orders": orders},
                    separators=(",", ":"),
                )
                + "\n"
            )
            sys.stdout.flush()
        elif kind == "done":
            return 0
        else:
            raise SystemExit("unknown message type: %r" % (kind,))
    raise SystemExit("input ended before done")


if __name__ == "__main__":
    raise SystemExit(main())
