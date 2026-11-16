"""Market structure: swings, HH/HL/LH/LL, BOS/CHoCH, levels, sweeps, breakouts."""

from __future__ import annotations

from dataclasses import dataclass

from app.market_data.models import Candle

BULLISH = "BULLISH"
BEARISH = "BEARISH"
RANGING = "RANGING"


@dataclass(frozen=True)
class Swing:
    index: int
    timestamp: int
    price: float
    kind: str  # "high" or "low"


@dataclass(frozen=True)
class StructureEvent:
    kind: str  # "BOS" or "CHoCH"
    direction: str
    price: float
    index: int


@dataclass(frozen=True)
class Level:
    price: float
    kind: str  # "support" or "resistance"
    touches: int
    strength: float


@dataclass(frozen=True)
class Sweep:
    direction: str  # BULLISH sweep of sell-side liquidity / BEARISH sweep of buy-side
    level: float
    confirmed: bool


@dataclass
class PriceActionResult:
    trend: str
    swing_highs: list[Swing]
    swing_lows: list[Swing]
    events: list[StructureEvent]
    supports: list[Level]
    resistances: list[Level]
    sweep: Sweep | None
    breakout_confirmed: bool
    false_breakout: bool
    retest: bool


def find_swings(candles: list[Candle], order: int = 2) -> tuple[list[Swing], list[Swing]]:
    """Confirm swing highs/lows with neighbouring bars (no look-ahead)."""
    highs: list[Swing] = []
    lows: list[Swing] = []
    if len(candles) < order * 2 + 1:
        return highs, lows
    for i in range(order, len(candles) - order):
        window = candles[i - order : i + order + 1]
        c = candles[i]
        if c.high >= max(x.high for x in window) and c.high > min(x.high for x in window):
            highs.append(Swing(i, c.timestamp, c.high, "high"))
        if c.low <= min(x.low for x in window) and c.low < max(x.low for x in window):
            lows.append(Swing(i, c.timestamp, c.low, "low"))
    return highs, lows


def classify_swings(swings: list[Swing]) -> list[str]:
    """Label transitions as HH/HL/LH/LL relative to the previous swing."""
    labels: list[str] = []
    for prev, cur in zip(swings, swings[1:]):
        if cur.price > prev.price:
            labels.append("HH" if cur.kind == "high" else "HL")
        else:
            labels.append("LH" if cur.kind == "high" else "LL")
    return labels


def structure_trend(highs: list[Swing], lows: list[Swing]) -> str:
    """Derive bullish/bearish/ranging structure from the last few swings."""
    if len(highs) < 2 or len(lows) < 2:
        return RANGING
    high_seq = [h.price for h in highs[-3:]]
    low_seq = [l.price for l in lows[-3:]]
    higher_highs = all(b > a for a, b in zip(high_seq, high_seq[1:]))
    lower_highs = all(b < a for a, b in zip(high_seq, high_seq[1:]))
    higher_lows = all(b > a for a, b in zip(low_seq, low_seq[1:]))
    lower_lows = all(b < a for a, b in zip(low_seq, low_seq[1:]))
    if higher_highs and higher_lows:
        return BULLISH
    if lower_highs and lower_lows:
        return BEARISH
    return RANGING


def detect_bos_choch(candles: list[Candle], highs: list[Swing], lows: list[Swing]) -> list[StructureEvent]:
    """Break of Structure vs Change of Character using closed candles only."""
    events: list[StructureEvent] = []
    combined = sorted([*highs, *lows], key=lambda s: s.index)
    broken_highs: set[int] = set()
    broken_lows: set[int] = set()

    for swing in combined:
        subsequent = candles[swing.index + 1 :]
        if not subsequent:
            continue
        breaking = None
        for offset, candle in enumerate(subsequent):
            idx = swing.index + 1 + offset
            if swing.kind == "high" and swing.index not in broken_highs:
                if candle.close > swing.price:
                    breaking = (idx, candle)
                    broken_highs.add(swing.index)
                    break
            elif swing.kind == "low" and swing.index not in broken_lows:
                if candle.close < swing.price:
                    breaking = (idx, candle)
                    broken_lows.add(swing.index)
                    break
        if breaking is None:
            continue

        idx, candle = breaking
        prior_highs = [s for s in highs if s.index < swing.index][-2:]
        prior_lows = [s for s in lows if s.index < swing.index][-2:]
        prior = structure_trend(prior_highs, prior_lows)
        if swing.kind == "high":
            kind = "CHoCH" if prior == BEARISH else "BOS"
            events.append(StructureEvent(kind, BULLISH, swing.price, idx))
        else:
            kind = "CHoCH" if prior == BULLISH else "BOS"
            events.append(StructureEvent(kind, BEARISH, swing.price, idx))

    events.sort(key=lambda e: e.index)
    return events


def find_levels(
    candles: list[Candle], highs: list[Swing], lows: list[Swing], tolerance: float = 0.004
) -> tuple[list[Level], list[Level]]:
    """Cluster historical reaction points into support/resistance zones."""
    if not candles:
        return [], []
    current = candles[-1].close

    def cluster(prices: list[float], kind: str) -> list[Level]:
        levels: list[Level] = []
        for price in sorted(prices):
            placed = False
            for level in levels:
                if abs(level.price - price) / max(price, 1e-9) <= tolerance:
                    new_price = (level.price * level.touches + price) / (level.touches + 1)
                    levels[levels.index(level)] = Level(new_price, kind, level.touches + 1, level.strength)
                    placed = True
                    break
            if not placed:
                levels.append(Level(price, kind, 1, 0.3))
        for level in levels:
            strength = min(1.0, 0.3 + 0.2 * (level.touches - 1))
            levels[levels.index(level)] = Level(level.price, kind, level.touches, strength)
        return levels

    resistance = [l for l in cluster([s.price for s in highs], "resistance") if l.price > current]
    support = [l for l in cluster([s.price for s in lows], "support") if l.price < current]
    resistance.sort(key=lambda l: l.price)
    support.sort(key=lambda l: -l.price)
    return support, resistance


def detect_sweep(candles: list[Candle], highs: list[Swing], lows: list[Swing]) -> Sweep | None:
    """Liquidity sweep: wick takes out a swing point but close returns inside."""
    if len(candles) < 2:
        return None
    last = candles[-1]
    recent_highs = [s.price for s in highs[-4:]]
    recent_lows = [s.price for s in lows[-4:]]
    for level in recent_highs:
        if last.high > level and last.close < level:
            return Sweep(BEARISH, level, last.close < min(c.close for c in candles[-3:]))
    for level in recent_lows:
        if last.low < level and last.close > level:
            return Sweep(BULLISH, level, last.close > max(c.close for c in candles[-3:]))
    return None


def analyze_breakout(
    candles: list[Candle], resistance: list[Level], support: list[Level]
) -> tuple[bool, bool, bool]:
    """Return (breakout_confirmed, false_breakout, retest)."""
    if len(candles) < 3:
        return False, False, False
    last, prev = candles[-1], candles[-2]
    breakout_confirmed = False
    false_breakout = False
    retest = False

    if resistance and prev.close > resistance[0].price:
        breakout_confirmed = True
        if last.close < resistance[0].price:
            false_breakout = True
        if last.low <= resistance[0].price <= last.high and last.close > resistance[0].price:
            retest = True
    elif support and prev.close < support[0].price:
        breakout_confirmed = True
        if last.close > support[0].price:
            false_breakout = True
        if last.high >= support[0].price >= last.low and last.close < support[0].price:
            retest = True
    return breakout_confirmed, false_breakout, retest


def analyze(candles: list[Candle], order: int = 2) -> PriceActionResult:
    """Run the full price-action analysis on closed candles."""
    highs, lows = find_swings(candles, order)
    events = detect_bos_choch(candles, highs, lows)
    supports, resistances = find_levels(candles, highs, lows)
    breakout, false_breakout, retest = analyze_breakout(candles, resistances, supports)
    return PriceActionResult(
        trend=structure_trend(highs, lows),
        swing_highs=highs,
        swing_lows=lows,
        events=events,
        supports=supports,
        resistances=resistances,
        sweep=detect_sweep(candles, highs, lows),
        breakout_confirmed=breakout and not false_breakout,
        false_breakout=false_breakout,
        retest=retest,
    )
