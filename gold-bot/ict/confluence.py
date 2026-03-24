"""Confluence scoring system for trade validation.

Minimum 3 confluences required to take a trade.
Categories:
  - Reversal (required): liquidity_sweep, pdh_pdl_sweep
  - Confirmation (min 1): bos, choch, ifvg, smt, fib_79
  - Continuation (min 1): fvg, ob, bb, eq
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config.settings import MIN_CONFLUENCES, CONFLUENCE_WEIGHTS


@dataclass
class ConfluenceResult:
    """Tracks all confluences found for a potential trade."""
    confluences: list[str] = field(default_factory=list)
    score: int = 0
    has_reversal: bool = False
    has_confirmation: bool = False
    has_continuation: bool = False

    REVERSAL_TYPES = {"liquidity_sweep", "pdh_pdl_sweep"}
    CONFIRMATION_TYPES = {"bos", "choch", "ifvg", "smt", "fib_79"}
    CONTINUATION_TYPES = {"fvg", "ob", "bb", "eq"}

    def add(self, confluence_type: str):
        """Add a confluence and update score."""
        if confluence_type in self.confluences:
            return  # No duplicates
        self.confluences.append(confluence_type)
        self.score += CONFLUENCE_WEIGHTS.get(confluence_type, 1)

        if confluence_type in self.REVERSAL_TYPES:
            self.has_reversal = True
        elif confluence_type in self.CONFIRMATION_TYPES:
            self.has_confirmation = True
        elif confluence_type in self.CONTINUATION_TYPES:
            self.has_continuation = True

    @property
    def is_valid(self) -> bool:
        """Check if minimum confluences are met."""
        return (
            len(self.confluences) >= MIN_CONFLUENCES
            and self.has_reversal
            and self.has_confirmation
            and self.has_continuation
        )

    @property
    def summary(self) -> str:
        return ", ".join(self.confluences)
