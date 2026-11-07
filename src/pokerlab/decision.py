"""Pot odds, break-even equity and the expected value of folding vs calling.

Setting (heads-up, hero facing one bet)::

    pot    chips in the middle before the opponent bet
    bet    the opponent's bet
    stack  effective stack: the most either player can still put in at this point
           (the smaller of the two stacks behind, before the bet)

If the bet is larger than the stack, only ``stack`` can be called and the excess
is returned, so the amount to call is ``call = min(bet, stack)``.

EV is measured relative to folding, so folding is worth exactly 0 (chips already
in the pot are sunk; they are not "ours" any more). If the hero calls, the final
pot is ``pot + 2 * call`` and the hero collects ``equity`` of it on average:

    EV(call) = equity * (pot + 2 * call) - call

Setting EV(call) = 0 gives the **break-even equity** (also "required equity")::

    break_even = call / (pot + 2 * call)

Pot odds express the same thing as a ratio: the hero risks ``call`` to win
``pot + call``, i.e. ``(pot + call) : call``.

These formulas are exact when the call ends the betting (the bet is all-in).
Otherwise they ignore the turn and river betting; that is added in M6 (ADR 0004).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DecisionError(ValueError):
    """Invalid chip amounts."""


class Verdict(Enum):
    CALL = "call"
    FOLD = "fold"
    CLOSE = "close"  # the confidence interval straddles break-even: run more samples

    @property
    def label(self) -> str:
        return {"call": "Call", "fold": "Fold", "close": "Too close to call"}[self.value]


@dataclass(frozen=True)
class Situation:
    pot: float
    bet: float
    stack: float

    def __post_init__(self) -> None:
        if self.pot < 0:
            raise DecisionError("The pot cannot be negative.")
        if self.bet <= 0:
            raise DecisionError("The opponent's bet must be more than 0.")
        if self.stack <= 0:
            raise DecisionError("The effective stack must be more than 0.")

    @property
    def call(self) -> float:
        """Chips the hero must put in to call (capped by the stack)."""
        return min(self.bet, self.stack)

    @property
    def is_all_in(self) -> bool:
        """True if calling leaves no chips behind, so no more betting can happen."""
        return self.bet >= self.stack

    @property
    def returned(self) -> float:
        """Part of the bet that cannot be called and goes back to the opponent."""
        return max(0.0, self.bet - self.stack)

    @property
    def final_pot(self) -> float:
        return self.pot + 2 * self.call

    @property
    def break_even_equity(self) -> float:
        return self.call / self.final_pot

    @property
    def pot_odds(self) -> float:
        """Odds offered, as X in ``X : 1``: chips won per chip risked."""
        return (self.pot + self.call) / self.call

    def ev_call(self, equity: float) -> float:
        return equity * self.final_pot - self.call


@dataclass(frozen=True)
class Decision:
    situation: Situation
    equity: float
    equity_ci95: tuple[float, float]

    @property
    def ev_fold(self) -> float:
        return 0.0

    @property
    def ev_call(self) -> float:
        return self.situation.ev_call(self.equity)

    @property
    def ev_call_ci95(self) -> tuple[float, float]:
        """EV is linear in equity, so the equity CI maps straight onto an EV CI."""
        lo, hi = self.equity_ci95
        return self.situation.ev_call(lo), self.situation.ev_call(hi)

    @property
    def margin(self) -> float:
        """Equity minus break-even equity: how much spare equity the call has."""
        return self.equity - self.situation.break_even_equity

    @property
    def verdict(self) -> Verdict:
        lo, hi = self.equity_ci95
        be = self.situation.break_even_equity
        if lo > be:
            return Verdict.CALL
        if hi < be:
            return Verdict.FOLD
        # The interval contains break-even (for an exact result: equity == break-even,
        # where calling and folding are worth the same).
        return Verdict.CLOSE


def decide(situation: Situation, equity: float, equity_ci95: tuple[float, float]) -> Decision:
    return Decision(situation, equity, equity_ci95)


def explain(decision: Decision, heads_up: bool = True) -> str:
    """Plain-language explanation of the maths behind the verdict."""
    s = decision.situation
    be, eq = s.break_even_equity, decision.equity
    lines = []
    if s.returned:
        lines.append(
            f"You can only call {_chips(s.call)} of the {_chips(s.bet)} bet (your effective "
            f"stack); the other {_chips(s.returned)} goes back to the opponent."
        )
    lines.append(
        f"Calling costs {_chips(s.call)} and makes a final pot of {_chips(s.final_pot)}, "
        f"so the call needs {be:.1%} equity to break even (pot odds {s.pot_odds:.1f} : 1)."
    )
    verdict = decision.verdict
    if verdict is Verdict.CALL:
        lines.append(
            f"Your estimated equity is {eq:.1%}, so calling earns about "
            f"{_chips(decision.ev_call, signed=True)} on average compared with folding."
        )
    elif verdict is Verdict.FOLD:
        lines.append(
            f"Your estimated equity is only {eq:.1%}, so calling loses about "
            f"{_chips(-decision.ev_call)} on average: folding is better."
        )
    else:
        lines.append(
            f"Your estimated equity of {eq:.1%} is too close to the break-even point to tell "
            "the two options apart; with Monte Carlo, more samples narrow the interval."
        )
    caveats = ["under the opponent range you assumed"]
    if heads_up:
        caveats.append("against one opponent")
    if not s.is_all_in:
        caveats.append(
            "and assuming no more betting on later streets (the turn and river are modelled in M6)"
        )
    lines.append("This holds " + ", ".join(caveats) + ".")
    return " ".join(lines)


def _chips(x: float, signed: bool = False) -> str:
    text = f"{x:+,.1f}" if signed else f"{x:,.1f}"
    text = text.removesuffix(".0")
    return f"{text} chips"
