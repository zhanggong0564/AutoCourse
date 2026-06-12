from __future__ import annotations


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def parse_progress(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if "%" in line and len(line) < 50:
            return line
    return None


def is_completed(text: str, completed_keywords: list[str]) -> bool:
    return contains_any(text, completed_keywords)


def is_quiz(text: str, quiz_keywords: list[str]) -> bool:
    weak_keywords = {"答题", "测验", "试题"}
    actionable_keywords = [
        keyword for keyword in quiz_keywords if keyword not in weak_keywords
    ]
    return contains_any(text, actionable_keywords)


def needs_human(text: str, human_keywords: list[str]) -> bool:
    return contains_any(text, human_keywords)


def course_candidate_priority(
    text: str,
    course_keywords: list[str],
    preferred_keywords: list[str],
    excluded_keywords: list[str],
) -> int | None:
    if contains_any(text, excluded_keywords):
        return None
    if not contains_any(text, course_keywords):
        return None
    return 0 if contains_any(text, preferred_keywords) else 1
