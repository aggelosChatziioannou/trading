"""High-impact news dates filter - skip trading on CPI/PPI/FOMC/NFP days."""
from datetime import date

# Major USD news events 2024-2025 (CPI, PPI, FOMC, NFP)
NEWS_BLACKOUT_DATES: set[date] = {
    # 2024 NFP
    date(2024, 1, 5), date(2024, 2, 2), date(2024, 3, 8), date(2024, 4, 5),
    date(2024, 5, 3), date(2024, 6, 7), date(2024, 7, 5), date(2024, 8, 2),
    date(2024, 9, 6), date(2024, 10, 4), date(2024, 11, 1), date(2024, 12, 6),
    # 2024 CPI
    date(2024, 1, 11), date(2024, 2, 13), date(2024, 3, 12), date(2024, 4, 10),
    date(2024, 5, 15), date(2024, 6, 12), date(2024, 7, 11), date(2024, 8, 14),
    date(2024, 9, 11), date(2024, 10, 10), date(2024, 11, 13), date(2024, 12, 11),
    # 2024 PPI
    date(2024, 1, 12), date(2024, 2, 16), date(2024, 3, 14), date(2024, 4, 11),
    date(2024, 5, 14), date(2024, 6, 13), date(2024, 7, 12), date(2024, 8, 13),
    date(2024, 9, 12), date(2024, 10, 11), date(2024, 11, 14), date(2024, 12, 12),
    # 2024 FOMC
    date(2024, 1, 31), date(2024, 3, 20), date(2024, 5, 1), date(2024, 6, 12),
    date(2024, 7, 31), date(2024, 9, 18), date(2024, 11, 7), date(2024, 12, 18),
    # 2025 NFP
    date(2025, 1, 10), date(2025, 2, 7), date(2025, 3, 7), date(2025, 4, 4),
    date(2025, 5, 2), date(2025, 6, 6), date(2025, 7, 3), date(2025, 8, 1),
    date(2025, 9, 5), date(2025, 10, 3), date(2025, 11, 7), date(2025, 12, 5),
    # 2025 CPI
    date(2025, 1, 15), date(2025, 2, 12), date(2025, 3, 12), date(2025, 4, 10),
    date(2025, 5, 13), date(2025, 6, 11), date(2025, 7, 15), date(2025, 8, 12),
    date(2025, 9, 10), date(2025, 10, 14), date(2025, 11, 12), date(2025, 12, 10),
    # 2025 PPI
    date(2025, 1, 14), date(2025, 2, 13), date(2025, 3, 13), date(2025, 4, 11),
    date(2025, 5, 15), date(2025, 6, 12), date(2025, 7, 15), date(2025, 8, 14),
    date(2025, 9, 11), date(2025, 10, 15), date(2025, 11, 13), date(2025, 12, 11),
    # 2025 FOMC
    date(2025, 1, 29), date(2025, 3, 19), date(2025, 5, 7), date(2025, 6, 18),
    date(2025, 7, 30), date(2025, 9, 17), date(2025, 10, 29), date(2025, 12, 17),
    # 2026 H1
    date(2026, 1, 9), date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 28),
    date(2026, 2, 6), date(2026, 2, 11), date(2026, 2, 12),
    date(2026, 3, 6), date(2026, 3, 11), date(2026, 3, 12), date(2026, 3, 18),
}


def is_news_blackout(d: date) -> bool:
    """Return True if the given date is a high-impact news day."""
    return d in NEWS_BLACKOUT_DATES
