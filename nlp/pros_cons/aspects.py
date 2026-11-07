"""Aspect lexicon and matcher.

An aspect is a product property shoppers talk about (durability, fit, taste...).
The dataset spans many categories (kitchen, clothing, grocery, beauty, auto,
baby, toys, sports), so v1 uses a curated cross-category lexicon instead of a
per-category model. Every match is traceable to the exact term that fired,
which keeps the output explainable for the dashboard.

Each term may carry an inherent polarity: "fell apart" is negative and
"leak proof" is positive even without a separate sentiment word.
Terms are matched on tokens, longest phrase first, and a token is used by at
most one term, so "easy to clean" counts as cleaning, not ease of use.

An aspect may also define pos_cues / neg_cues: tokens anywhere in the same
clause that reveal polarity for that aspect only ("keeps my water cold all
day" is positive for temperature although no sentiment word appears).
"""

from __future__ import annotations

from dataclasses import dataclass


# term -> inherent polarity: +1 positive, -1 negative, 0 none
ASPECT_LEXICON: dict[str, dict] = {
    "quality": {
        "label": "Build quality",
        "terms": {
            "quality": 0, "well made": 1, "well built": 1, "sturdy": 1, "solid": 1,
            "solid build": 1, "built solid": 1,
            "flimsy": -1, "cheaply made": -1, "feels cheap": -1, "looks cheap": -1,
            "poorly made": -1, "construction": 0, "craftsmanship": 0,
        },
    },
    "durability": {
        "label": "Durability",
        "terms": {
            "durable": 1, "durability": 0, "lasted": 0, "lasts": 0, "long lasting": 1,
            "broke": -1, "broken": -1, "breaks": -1, "fell apart": -1,
            "falling apart": -1, "ripped": -1, "tore": -1, "torn": -1,
            "wore out": -1, "worn out": -1, "cracked": -1, "peeling": -1,
            "chipped": -1, "holes": -1, "stopped working": -1, "quit working": -1,
        },
    },
    "value": {
        "label": "Price & value",
        "terms": {
            "price": 0, "priced": 0, "value": 0, "worth": 0, "money": 0,
            "expensive": -1, "overpriced": -1, "affordable": 1, "bargain": 1,
            "great deal": 1, "good deal": 1, "cost": 0, "cheaper": 0,
            "cost effective": 1,
            "worth the money": 1, "waste of money": -1, "inexpensive": 1,
        },
    },
    "size_fit": {
        "label": "Size & fit",
        "terms": {
            "size": 0, "sizing": 0, "fit": 0, "fits": 0, "fitting": 0,
            "true to size": 1, "runs small": -1, "runs large": -1, "runs big": -1,
            "run small": -1, "run large": -1, "run big": -1,
            "too small": -1, "too big": -1, "too large": -1, "too tight": -1,
            "too loose": -1, "tight": 0, "loose": 0, "snug": 0, "perfect fit": 1,
        },
    },
    "comfort": {
        "label": "Comfort",
        "terms": {
            "comfortable": 1, "comfort": 0, "comfy": 1, "uncomfortable": -1,
            "soft": 1, "cushion": 0, "cushioning": 0, "itchy": -1, "scratchy": -1,
        },
    },
    "ease_of_use": {
        "label": "Ease of use",
        "terms": {
            "easy to use": 1, "easy": 0, "simple": 0, "convenient": 1,
            "user friendly": 1, "hard to use": -1, "difficult": -1,
            "complicated": -1, "setup": 0, "set up": 0, "install": 0,
            "installation": 0, "assemble": 0, "assembly": 0, "instructions": 0,
        },
    },
    "cleaning": {
        "label": "Easy to clean",
        "terms": {
            "easy to clean": 1, "hard to clean": -1, "difficult to clean": -1,
            "clean": 0, "cleaning": 0, "hand wash": 0,
            "dishwasher": 0, "dishwasher safe": 1, "mold": -1, "moldy": -1,
        },
    },
    "leaks": {
        "label": "Leak resistance",
        "terms": {
            "leak": -1, "leaks": -1, "leaking": -1, "leaked": -1, "leaky": -1,
            "leak proof": 1, "leakproof": 1, "spill": 0, "spills": -1,
            "spilled": -1, "drips": -1, "dripping": -1,
        },
    },
    "temperature": {
        "label": "Keeps temperature",
        "terms": {
            "cold": 0, "colder": 0, "ice": 0, "insulated": 0, "insulation": 0,
            "hot": 0, "warm": 0, "temperature": 0, "keeps drinks cold": 1,
            "stays cold": 1, "stays hot": 1, "keeps it cold": 1,
        },
        # Context cues: words elsewhere in the clause that reveal polarity.
        "pos_cues": {"keeps", "kept", "keep", "stays", "stayed", "hours", "overnight"},
        "neg_cues": {"lukewarm", "melts", "melted", "sweats", "sweating", "condensation"},
    },
    "taste": {
        "label": "Taste & flavor",
        "terms": {
            "taste": 0, "tastes": 0, "tasted": 0, "tasty": 1, "flavor": 0,
            "flavors": 0, "flavour": 0, "delicious": 1, "aftertaste": -1,
            "bland": -1, "sweet": 0, "too sweet": -1,
        },
    },
    "scent": {
        "label": "Smell & scent",
        "terms": {
            "smell": 0, "smells": 0, "scent": 0, "scents": 0, "scented": 0,
            "fragrance": 0, "odor": 0, "odour": 0, "stinks": -1, "smelly": -1,
        },
    },
    "skin": {
        "label": "Skin feel",
        "terms": {
            "skin": 0, "gentle": 1, "moisturizing": 1, "hydrating": 1,
            "irritation": -1, "irritated": -1, "breakout": -1, "breakouts": -1,
            "broke me out": -1, "rash": -1, "burning": -1, "greasy": -1,
        },
    },
    "battery": {
        "label": "Battery & charging",
        "terms": {
            "battery": 0, "batteries": 0, "battery life": 0, "charge": 0,
            "charging": 0, "charger": 0, "charges": 0,
        },
    },
    "performance": {
        "label": "Performance",
        "terms": {
            "works": 0, "worked": 0, "performance": 0, "performs": 0,
            "effective": 1, "ineffective": -1, "powerful": 1, "does the job": 1,
            "does the trick": 1, "doesn't work": -1, "didn't work": -1,
            "not work": -1, "useless": -1,
        },
    },
    "appearance": {
        "label": "Look & design",
        "terms": {
            "looks": 0, "look": 0, "color": 0, "colors": 0, "colour": 0,
            "design": 0, "cute": 1, "pretty": 1, "beautiful": 1, "stylish": 1,
            "style": 0, "ugly": -1, "faded": -1,
        },
    },
    "material": {
        "label": "Material",
        "terms": {
            "material": 0, "materials": 0, "fabric": 0, "cotton": 0, "plastic": 0,
            "stainless steel": 0, "rubber": 0, "texture": 0, "thin": 0, "thick": 0,
        },
    },
    "packaging_shipping": {
        "label": "Packaging & delivery",
        "terms": {
            "packaging": 0, "packaged": 0, "arrived": 0,
            "shipping": 0, "delivery": 0, "delivered": 0, "damaged": -1,
            "arrived damaged": -1, "dented": -1, "missing": -1,
        },
    },
    "seller_service": {
        "label": "Seller & returns",
        "terms": {
            "customer service": 0, "seller": 0, "refund": 0, "replacement": 0,
            "warranty": 0, "returned": -1, "returning": -1, "return it": -1,
            "sent it back": -1,
        },
    },
    "noise": {
        "label": "Noise",
        "terms": {"noise": 0, "noisy": -1, "loud": 0, "quiet": 1},
    },
    "weight": {
        "label": "Weight & portability",
        "terms": {
            "lightweight": 1, "heavy": 0, "weight": 0, "weighs": 0,
            "portable": 1, "bulky": -1,
        },
    },
}


# Words that are only an aspect when used as a predicate ("it's pretty",
# "feels solid"). Followed by another word they are usually something else:
# "pretty fast" (= quite), "solid color" (= plain), "a solid 4/5".
PREDICATE_ONLY_TERMS = {"pretty", "solid"}
PREDICATE_FOLLOWERS = {
    "and", "or", "but", "too", "enough", "as", "for", "with", "to", "in", "on",
    "overall", "though", "looking", "also",
}


@dataclass(frozen=True)
class AspectHit:
    """One aspect term found in a clause."""
    aspect: str
    term: str
    start: int           # token index where the term starts
    inherent: int        # inherent polarity of the term (-1, 0, +1)


class AspectMatcher:
    """Find aspect terms in a token list, longest phrase first."""

    def __init__(self, lexicon: dict[str, dict] | None = None):
        self.lexicon = lexicon or ASPECT_LEXICON
        self.index: dict[tuple[str, ...], tuple[str, str, int]] = {}
        for aspect, spec in self.lexicon.items():
            for term, polarity in spec["terms"].items():
                key = tuple(term.lower().split())
                if key in self.index and self.index[key][0] != aspect:
                    raise ValueError(f"Term '{term}' is assigned to two aspects")
                self.index[key] = (aspect, term, int(polarity))
        self.max_len = max(len(k) for k in self.index)

    def label(self, aspect: str) -> str:
        return self.lexicon[aspect]["label"]

    def cue_polarity(self, aspect: str, tokens: list[str]) -> int:
        """+1 / -1 from the aspect's context cues found in the clause, else 0.

        A negated cue flips: "doesn't keep food cold" is negative.
        """
        # Local import avoids a circular import (sentiment -> text only).
        from nlp.pros_cons.sentiment import is_negated

        spec = self.lexicon[aspect]
        pos_cues = spec.get("pos_cues", set())
        neg_cues = spec.get("neg_cues", set())
        total = 0
        for i, tok in enumerate(tokens):
            if tok in pos_cues:
                value = 1
            elif tok in neg_cues:
                value = -1
            else:
                continue
            total += -value if is_negated(tokens, i) else value
        return max(-1, min(1, total))

    @staticmethod
    def _is_modifier_use(tokens: list[str], i: int) -> bool:
        """True when a predicate-only word modifies the next word."""
        return (
            tokens[i] in PREDICATE_ONLY_TERMS
            and i + 1 < len(tokens)
            and tokens[i + 1] not in PREDICATE_FOLLOWERS
        )

    def find(self, tokens: list[str]) -> list[AspectHit]:
        hits: list[AspectHit] = []
        i = 0
        while i < len(tokens):
            matched = False
            # Try the longest phrase first so specific terms beat generic ones.
            for n in range(min(self.max_len, len(tokens) - i), 0, -1):
                key = tuple(tokens[i:i + n])
                if n == 1 and self._is_modifier_use(tokens, i):
                    break
                if key in self.index:
                    aspect, term, polarity = self.index[key]
                    hits.append(AspectHit(aspect, term, i, polarity))
                    i += n
                    matched = True
                    break
            if not matched:
                i += 1
        return hits
