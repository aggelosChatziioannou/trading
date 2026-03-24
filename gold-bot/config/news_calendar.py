"""High-impact news dates to avoid trading."""
from datetime import date

# 2025 H2 + 2026 H1 high-impact USD news dates
# CPI, PPI, FOMC, NFP
NEWS_BLACKOUT_DATES: set[date] = {
    # 2025
    date(2025, 7, 11), date(2025, 7, 15), date(2025, 7, 30),
    date(2025, 8, 1), date(2025, 8, 12), date(2025, 8, 14),
    date(2025, 9, 5), date(2025, 9, 10), date(2025, 9, 11), date(2025, 9, 17),
    date(2025, 10, 3), date(2025, 10, 14), date(2025, 10, 15), date(2025, 10, 29),
    date(2025, 11, 7), date(2025, 11, 12), date(2025, 11, 13),
    date(2025, 12, 5), date(2025, 12, 10), date(2025, 12, 11), date(2025, 12, 17),
    # 2026
    date(2026, 1, 9), date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 28),
    date(2026, 2, 6), date(2026, 2, 11), date(2026, 2, 12),
    date(2026, 3, 6), date(2026, 3, 11), date(2026, 3, 12), date(2026, 3, 18),
}


def is_news_blackout(d: date) -> bool:
    """Return True if the given date is a high-impact news day."""
    return d in NEWS_BLACKOUT_DATES
