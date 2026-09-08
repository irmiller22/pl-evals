"""Explicit POC team aliases; unknown names never silently match."""

import re


def canonical_name(source_name: str) -> str:
    return re.sub(r"\s+fc$", "", source_name.strip(), flags=re.IGNORECASE)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


ALIASES = {
    # Explicit shorthand required by the plan's natural-language demonstration.
    "united": "Manchester United",
    "man united": "Manchester United",
    "man utd": "Manchester United",
    "manchester utd": "Manchester United",
    "man city": "Manchester City",
    "spurs": "Tottenham Hotspur",
    "tottenham": "Tottenham Hotspur",
    "wolves": "Wolverhampton Wanderers",
    "brighton": "Brighton & Hove Albion",
    "bournemouth": "AFC Bournemouth",
    "west ham": "West Ham United",
    "newcastle": "Newcastle United",
    "nottingham forest": "Nottingham Forest",
}


def normalize_team(value: str, teams: set[str]) -> str:
    key = " ".join(canonical_name(value).casefold().split())
    names = {team.casefold(): team for team in teams}
    candidate = ALIASES.get(key, names.get(key))
    if candidate not in teams:
        raise ValueError(f"Unknown team in the loaded season: {value!r}")
    return candidate
