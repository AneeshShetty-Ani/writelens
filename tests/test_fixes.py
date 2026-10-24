from fixes import apply_fixes
from plagiarism import quote_and_cite


def test_replaces_wordy_phrases_keeping_capitals():
    r = apply_fixes("Due to the fact that it rained, we left in order to rest.")
    assert r.text == "Because it rained, we left to rest."
    assert ("due to the fact that", "because", 1) in r.changes


def test_deleted_opener_capitalises_next_word():
    r = apply_fixes("It is important to note that the results were good. Needless to say, we won.")
    assert r.text == "The results were good. We won."


def test_deleted_phrase_mid_sentence():
    assert apply_fixes("We think it should be noted that cats purr.").text == "We think cats purr."


def test_drops_filler_words():
    r = apply_fixes("The meeting was very useful and we really liked it. Basically, it worked.")
    assert r.text == "The meeting was useful and we liked it. It worked."
    assert ("very", "", 1) in r.changes and ("basically", "", 1) in r.changes


def test_keeps_fillers_that_carry_meaning():
    text = "Thank you very much. I am not really sure."
    assert apply_fixes(text).text == text


def test_expands_safe_contractions_only():
    r = apply_fixes("Don't panic. It isn't very big, I'm sure we can't lose. They’re here. Let's go.")
    assert r.text == "Do not panic. It is not very big, I am sure we cannot lose. They are here. Let us go."
    assert ("don't", "do not", 1) in r.changes and ("they're", "they are", 1) in r.changes


def test_leaves_ambiguous_contractions():
    # it's = it is / it has, he'd = he would / he had, ain't = am / is / are not
    text = "It's late and he'd left, but it ain't over."
    assert apply_fixes(text).text == text


def test_clean_text_unchanged():
    r = apply_fixes("Cats chase mice.\n\nDogs bark.")
    assert r.text == "Cats chase mice.\n\nDogs bark." and r.changes == []


def test_quote_and_cite():
    text = "Intro. plants use sunlight to make food every day."
    start = text.index("plants")
    end = text.index(" every")
    assert quote_and_cite(text, [(start, end, "(Wikipedia, 2024)")]) == (
        'Intro. "plants use sunlight to make food" (Wikipedia, 2024) every day.'
    )


def test_quote_and_cite_skips_quoted_and_overlapping():
    text = 'He said "copied words here" and more copied words.'
    q = text.index("copied")
    assert quote_and_cite(text, [(q, q + 17, "[1]")]) == text
    assert quote_and_cite("abcdef", [(0, 4, ""), (2, 6, "")]) == '"abcd"ef'
