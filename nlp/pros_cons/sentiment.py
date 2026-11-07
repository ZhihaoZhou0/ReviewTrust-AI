"""Clause-level sentiment scoring.

Two interchangeable backends share one interface, score(clause) -> float in [-1, 1]:

* "lexicon" (default): small built-in word lists with negation handling.
  No downloads, deterministic, fast enough for 250K reviews on a laptop.
* "vader": VADER compound score (pip install vaderSentiment). Optional,
  used as a comparison baseline in the evaluation.
"""

from __future__ import annotations

import math

from nlp.pros_cons.text import tokenize


POSITIVE_WORDS = {
    "good", "great", "excellent", "amazing", "awesome", "perfect", "perfectly",
    "love", "loved", "loves", "like", "liked", "nice", "best", "fantastic",
    "wonderful", "happy", "pleased", "impressed", "recommend", "recommended",
    "sturdy", "durable", "comfortable", "comfy", "soft", "easy", "easily",
    "convenient", "reliable", "fast", "quick", "quickly", "strong", "works",
    "worth", "affordable", "delicious", "tasty", "fresh", "cute", "pretty",
    "beautiful", "gentle", "smooth", "quiet", "lightweight", "effective",
    "fine", "solid", "superb", "satisfied", "favorite", "favourite", "glad",
    "helpful", "efficient", "secure", "clean", "cool", "refreshing",
    "flawless", "exceeded", "exceeds", "stylish", "elegant", "adorable",
    "well", "better", "decent", "sleek", "handy", "useful", "fits",
}

NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "horrible", "poor", "poorly", "worst", "worse",
    "hate", "hated", "disappointed", "disappointing", "disappointment",
    "broke", "broken", "breaks", "cheap", "cheaply", "flimsy", "defective",
    "useless", "waste", "junk", "garbage", "uncomfortable", "difficult",
    "hard", "leak", "leaks", "leaking", "leaked", "smells", "stinks",
    "smelly", "sticky", "slow", "noisy", "loud", "expensive", "overpriced",
    "tight", "itchy", "scratchy", "damaged", "missing", "wrong", "fake",
    "problem", "problems", "issue", "issues", "annoying", "faulty", "weak",
    "thin", "flimsy", "ripped", "torn", "cracked", "peeling", "faded",
    "bland", "gross", "unfortunately", "return", "returned", "refund",
    "complaint", "fails", "failed", "failure", "stopped", "rough", "mold",
    "moldy", "irritation", "irritated", "rash", "greasy", "bulky", "ugly",
    "lukewarm", "dented", "unusable", "unreliable", "mess", "messy",
}

NEGATORS = {
    "not", "no", "never", "none", "nothing", "neither", "nor", "without",
    "hardly", "barely", "don't", "doesn't", "didn't", "isn't", "wasn't",
    "aren't", "weren't", "won't", "wouldn't", "can't", "cannot", "couldn't",
    "shouldn't", "haven't", "hasn't", "hadn't", "dont", "doesnt", "didnt",
    "isnt", "wasnt", "wont", "cant", "couldnt",
}

INTENSIFIERS = {"very", "really", "so", "extremely", "super", "incredibly", "absolutely", "too", "pretty"}

NEGATION_WINDOW = 3


def is_negated(tokens: list[str], position: int, window: int = NEGATION_WINDOW) -> bool:
    """True if a negator appears within `window` tokens before `position`."""
    start = max(0, position - window)
    return any(t in NEGATORS for t in tokens[start:position])


def _normalize(raw: float, alpha: float = 4.0) -> float:
    """Squash an unbounded sum into [-1, 1] (same form VADER uses)."""
    return raw / math.sqrt(raw * raw + alpha)


class LexiconSentiment:
    """Word-count sentiment with negation and simple intensifiers."""

    name = "lexicon"

    def raw_score(self, tokens: list[str]) -> float:
        total = 0.0
        for i, tok in enumerate(tokens):
            # "pretty fast" / "pretty bad": pretty only intensifies the next word.
            if tok == "pretty" and i + 1 < len(tokens):
                continue
            if tok in POSITIVE_WORDS:
                value = 1.0
            elif tok in NEGATIVE_WORDS:
                value = -1.0
            else:
                continue
            if i > 0 and tokens[i - 1] in INTENSIFIERS:
                value *= 1.5
            if is_negated(tokens, i):
                value *= -0.75   # "not great" is weaker than "bad"
            total += value
        return total

    def score(self, clause: str) -> float:
        return _normalize(self.raw_score(tokenize(clause)))


class VaderSentiment:
    """VADER compound score; requires the optional vaderSentiment package."""

    name = "vader"

    def __init__(self):
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The vader backend needs: pip install vaderSentiment"
            ) from exc
        self._analyzer = SentimentIntensityAnalyzer()

    def score(self, clause: str) -> float:
        return float(self._analyzer.polarity_scores(clause)["compound"])


def get_sentiment_scorer(name: str = "lexicon"):
    """Factory used by scripts: 'lexicon' or 'vader'."""
    if name == "lexicon":
        return LexiconSentiment()
    if name == "vader":
        return VaderSentiment()
    raise ValueError(f"Unknown sentiment backend: {name}")
