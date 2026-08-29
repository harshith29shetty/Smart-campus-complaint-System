"""
Rule-Based Priority Engine for Campus Complaints.

Assigns a priority level (Low / Medium / High) to a complaint based on
keyword matching and duration indicators, and produces a human-readable
explanation for the decision — useful both for the admin dashboard and
for explaining the system in a viva.

Design notes:
- This is an explainable, rule-based system — easy to audit and describe.
- Keyword rules take precedence over duration-only rules.
- This is an ACADEMIC prioritization system, not a safety-certified tool.
"""

import re
from typing import Tuple

HIGH_KEYWORDS = [
    "urgent", "emergency", "danger", "dangerous", "unsafe",
    "fire", "shock", "electric shock", "electrical hazard", "short circuit",
    "hazard", "flooding", "water flooding", "flood",
    "not working", "completely stopped", "completely broken", "completely dead",
    "security issue", "security threat", "ragging",
    "no water", "no power", "no internet", "no electricity",
    "sparking", "spark", "burning smell", "smoke", "catching fire",
    "leak", "burst", "sewage overflow", "overflow",
    "food poisoning", "fell ill", "feeling sick", "health hazard",
    "exposed wire", "live wire", "bare wire",
    "collapsed", "cracked", "broken glass", "sharp edges",
    "injury", "hurt", "accident",
    "pest", "cockroach", "rat", "rodent", "insects in food",
]

MEDIUM_KEYWORDS = [
    "slow", "not proper", "not clean", "dirty", "poor",
    "problem", "issue", "not available", "unavailable",
    "frequently", "often", "sometimes", "intermittent",
    "broken", "damaged", "faulty", "malfunctioning",
    "no option", "insufficient", "inadequate",
    "flickering", "noise", "smell", "odor",
    "very low", "too low", "too high", "too slow",
    "stale", "unhygienic", "not maintained",
]

_DURATION_PATTERNS = [
    r"\bsince\s+(yesterday|last\s+\w+|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bfor\s+(two|three|four|five|six|seven|several|many|multiple|\d+)\s+(days?|weeks?|hours?)\b",
    r"\bpast\s+(two|three|four|five|six|seven|several|many|\d+)\s+(days?|weeks?|hours?)\b",
    r"\b(days?|weeks?)\s+ago\b",
    r"\bsince\s+\d+\s+(days?|weeks?)\b",
    r"\bfrom\s+(two|three|four|five|six|seven|several|many|\d+)\s+(days?|weeks?)\b",
    r"\bnot\s+working\s+since\b",
    r"\bhas\s+been\s+(broken|not working|down|faulty|damaged)\b",
]
_COMPILED_DURATION = [re.compile(p, re.IGNORECASE) for p in _DURATION_PATTERNS]


def _find_matching_keywords(text: str, keyword_list: list) -> list:
    text_lower = text.lower()
    return [kw for kw in keyword_list if kw in text_lower]


def _find_duration_indicators(text: str) -> list:
    matches = []
    for pattern in _COMPILED_DURATION:
        m = pattern.search(text)
        if m:
            matches.append(m.group(0))
    return matches


def predict_priority_with_explanation(title: str, description: str) -> Tuple[str, str]:
    """
    Returns (priority, explanation).
    priority: "High" | "Medium" | "Low"
    explanation: human-readable string explaining the decision.
    """
    combined_text = f"{title} {description}"

    high_matches = _find_matching_keywords(combined_text, HIGH_KEYWORDS)
    medium_matches = _find_matching_keywords(combined_text, MEDIUM_KEYWORDS)
    duration_matches = _find_duration_indicators(combined_text)

    reasons = []

    if high_matches:
        priority = "High"
        trigger_words = ", ".join([f'"{kw}"' for kw in high_matches[:3]])
        reasons.append(f"Contains urgent or safety-related indicators ({trigger_words}).")
        if duration_matches:
            reasons.append(f"The issue has also been ongoing ({duration_matches[0]}), increasing urgency.")

    elif duration_matches and medium_matches:
        priority = "High"
        reasons.append(
            f"Describes a significant issue (e.g. \"{medium_matches[0]}\") "
            f"that has continued for an extended period ({duration_matches[0]})."
        )

    elif duration_matches:
        priority = "Medium"
        reasons.append(f"The issue has been ongoing ({duration_matches[0]}), which warrants prompt attention.")

    elif medium_matches:
        priority = "Medium"
        trigger_words = ", ".join([f'"{kw}"' for kw in medium_matches[:2]])
        reasons.append(f"Describes an issue requiring attention ({trigger_words}).")

    else:
        priority = "Low"
        reasons.append("Describes a general or non-urgent issue; no urgent keywords or duration indicators detected.")

    explanation = " ".join(reasons)
    return priority, explanation


def detect_priority(text: str) -> str:
    """Backward-compatible simple wrapper — returns just the priority string."""
    priority, _ = predict_priority_with_explanation("", text)
    return priority
