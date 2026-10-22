from analysis import analyze, count_syllables, split_sentences


def test_empty_text():
    r = analyze("   ")
    assert r.words == 0 and r.sentences == 0 and r.wordy == []


def test_counts():
    r = analyze("One two three. Four five!")
    assert r.words == 5
    assert r.sentences == 2
    assert r.avg_sentence_len == 2.5


def test_wordy_phrase_case_insensitive():
    r = analyze("Due to the fact that it rained, we left. due to the fact that.")
    assert ("due to the fact that", "because", 2) in r.wordy


def test_wordy_phrase_needs_word_boundaries():
    # "this able to" contains "is able to" as a substring but is not that phrase.
    r = analyze("We found this able to work.")
    assert all(p != "is able to" for p, _, _ in r.wordy)


def test_overlapping_wordy_phrases_counted_once():
    r = analyze("Due to the fact that it rained, we left. The fact that it rained is clear.")
    assert ("due to the fact that", "because", 1) in r.wordy
    assert ("the fact that", "that", 1) in r.wordy


def test_wordy_phrase_with_words_before_it():
    r = analyze("It is very clearly important to note that we won.")
    assert any(p == "important to note" for p, _, _ in r.wordy)


def test_long_sentence_flagged():
    long = " ".join(["word"] * 35) + "."
    r = analyze(long + " Short one.")
    assert r.long_sentences == [long]


def test_syllables():
    assert count_syllables("cat") == 1
    assert count_syllables("table") == 2
    assert count_syllables("make") == 1
    assert count_syllables("readability") >= 4


def test_split_sentences():
    assert split_sentences("Hi there. How are you? Fine!") == ["Hi there.", "How are you?", "Fine!"]


def test_split_keeps_abbreviations():
    text = "Dr. Smith agreed, e.g. in Fig. 2. Smith et al. disagreed."
    assert split_sentences(text) == ["Dr. Smith agreed, e.g. in Fig. 2.", "Smith et al. disagreed."]


def test_split_on_line_breaks():
    assert split_sentences("Introduction\nThis is the start.") == ["Introduction", "This is the start."]
