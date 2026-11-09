"""Univers suivi : les 30 titres du Dow Jones de février 2018, jeu de référence du projet."""

from __future__ import annotations

COMPANIES = {
    "AAPL": "Apple",
    "AXP": "American Express",
    "BA": "Boeing",
    "CAT": "Caterpillar",
    "CSCO": "Cisco",
    "CVX": "Chevron",
    "DIS": "Disney",
    "DWDP": "DowDuPont",
    "GE": "General Electric",
    "GS": "Goldman Sachs",
    "HD": "Home Depot",
    "IBM": "IBM",
    "INTC": "Intel",
    "JNJ": "Johnson & Johnson",
    "JPM": "JPMorgan",
    "KO": "Coca-Cola",
    "MCD": "McDonald's",
    "MMM": "3M",
    "MRK": "Merck",
    "MSFT": "Microsoft",
    "NKE": "Nike",
    "PFE": "Pfizer",
    "PG": "Procter & Gamble",
    "TRV": "Travelers",
    "UNH": "UnitedHealth",
    "UTX": "United Technologies",
    "V": "Visa",
    "VZ": "Verizon",
    "WMT": "Walmart",
    "XOM": "ExxonMobil",
}


def company_name(ticker: str) -> str:
    """Renvoie le nom de la société, ou le ticker s'il est inconnu."""
    return COMPANIES.get(ticker, ticker)
