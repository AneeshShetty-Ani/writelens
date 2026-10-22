"""spaCy-based checks: passive voice, repeated words, weak verbs, and adverbs."""

from collections import Counter
from dataclasses import dataclass, field

import streamlit as st

WEAK_VERBS = {"be", "have", "do", "get", "make", "go", "seem", "become", "put", "take"}
ADVERB_WATCHLIST = {
    "very", "really", "quite", "extremely", "basically", "actually", "totally", "literally", "rather", "pretty",
}
# "-ly" adverbs that usually carry meaning rather than filler.
LY_ADVERB_KEEP = {"only", "early", "daily", "weekly", "monthly", "yearly", "likely", "rarely", "directly", "newly"}
REPEAT_MIN = 3


@dataclass
class NlpReport:
    available: bool = True
    passive: list[str] = field(default_factory=list)
    repeated: list[tuple[str, int]] = field(default_factory=list)
    weak_verbs: list[tuple[str, int]] = field(default_factory=list)
    adverbs: list[tuple[str, int]] = field(default_factory=list)


@st.cache_resource(show_spinner="Loading language model...")
def load_nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        return None


def is_passive(sent) -> bool:
    return any(tok.dep_ in ("nsubjpass", "auxpass") for tok in sent)


def is_filler_adverb(tok) -> bool:
    word = tok.lower_
    if word in ADVERB_WATCHLIST:
        # "pretty" is only filler as an adverb ("pretty good"), not in "a pretty garden".
        return word != "pretty" or tok.pos_ == "ADV"
    return tok.pos_ == "ADV" and word.endswith("ly") and word not in LY_ADVERB_KEEP


def check(text: str) -> NlpReport:
    nlp = load_nlp()
    if nlp is None:
        return NlpReport(available=False)

    doc = nlp(text)
    report = NlpReport()

    report.passive = [s.text.strip() for s in doc.sents if is_passive(s)]

    content = Counter(
        tok.lemma_.lower()
        for tok in doc
        if tok.is_alpha and not tok.is_stop and tok.pos_ in ("NOUN", "VERB", "ADJ")
    )
    report.repeated = [(w, n) for w, n in content.most_common() if n >= REPEAT_MIN]

    # Main verbs only; skip auxiliaries like "was" in "was thrown".
    weak = Counter(
        tok.lemma_.lower()
        for tok in doc
        if tok.pos_ == "VERB" and tok.dep_ != "aux" and tok.lemma_.lower() in WEAK_VERBS
    )
    report.weak_verbs = weak.most_common()

    adverbs = Counter(tok.lower_ for tok in doc if is_filler_adverb(tok))
    report.adverbs = adverbs.most_common()

    return report
