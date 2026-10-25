from analysis import (
    analyze, count_syllables, duration, expand_contraction, find_misspellings, repeated_start_runs, split_sentences,
)


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


def test_cliches_counted():
    r = analyze("Last but not least, we must Think Outside The Box. We think outside the box daily.")
    assert r.cliches == [("think outside the box", 2), ("last but not least", 1)]


def test_contractions_found_but_not_possessives():
    r = analyze("We don't know. It’s late, and Sam's car can't start. They'd left. I'm here.")
    words = dict(r.contractions)
    assert words == {"don't": 1, "it's": 1, "can't": 1, "they'd": 1, "i'm": 1}
    assert "sam's" not in words
    assert analyze("O'Neill wrote it.").contractions == []


def test_expand_contraction():
    assert expand_contraction("don't") == "do not"
    assert expand_contraction("Can’t") == "cannot"
    assert expand_contraction("won't") == "will not"
    assert expand_contraction("they're") == "they are"
    assert expand_contraction("I've") == "I have"
    assert expand_contraction("it's") == "it is / has"


def test_mixed_spelling_reports_both_and_the_fewer():
    r = analyze("We analysed the colour data, organised it, then organized the centre.")
    assert dict(r.uk_spelling) == {"analysed": 1, "colour": 1, "organised": 1, "centre": 1}
    assert dict(r.us_spelling) == {"organized": 1}
    assert r.minority_spelling == [("organized", 1)]


def test_consistent_spelling_is_not_flagged():
    for text in ("We analysed the colour of the centre.", "We analyzed the color of the center.",
                 "The analyses were realistic; a literal meter of labor."):
        r = analyze(text)
        assert r.uk_spelling == [] and r.us_spelling == [], text


def test_sentence_lengths_and_variety():
    same = analyze(" ".join(["The cat sat on the warm mat today."] * 6))
    assert same.sentence_lengths == [8] * 6 and same.monotonous
    mixed = analyze("Stop. The cat sat on the mat. Then, after a very long and tiring day of chasing birds around "
                    "the garden, it finally fell asleep. Good. It dreamt of fish and mice all night.")
    assert not mixed.monotonous
    assert not analyze("Same length here. Same length here.").monotonous  # too few sentences to judge


def test_misspellings_found_with_fixes():
    found = find_misspellings("I recieve teh results and definately agree.")
    assert found == [("definately", "definitely", 1), ("recieve", "receive", 1), ("teh", "the", 1)]


def test_spelling_skips_names_links_uk_and_terms():
    text = ("Aneesh and Priyanka visited Bengaluru. See https://exampel.com/pagee or mail me@exampel.com. "
            "We organised the urbanisation programme and analysed the colour data. "
            "The hyperparameters were tuned. The zorbix model beat the zorbix baseline; zorbix wins.")
    assert find_misspellings(text) == []


def test_informal_words_and_second_person():
    r = analyze("You should know that you can do it. Your work is gonna be awesome, with a lot of stuff.")
    assert r.informal == [("a lot of", "many / much", 1), ("awesome", "excellent", 1), ("gonna", "going to", 1),
                          ("stuff", "a specific word (material, items...)", 1)]
    assert r.second_person == 3
    assert analyze("As you know, the results were clear.").second_person == 0  # once is fine


def test_repeated_sentence_starts():
    sentences = ["The cat ran.", "The dog sat.", "The bird sang.", "A fish swam.", "It was.", "It is.", "It ends."]
    assert repeated_start_runs(sentences) == [("the", 0, 3), ("it", 4, 3)]
    assert repeated_start_runs(["The a.", "The b.", "A c.", "The d."]) == []
    assert analyze("The cat ran. The dog sat. The bird sang.").repeated_starts == [("the", 0, 3)]


def test_weak_openings_only_in_the_opening():
    r = analyze("In today's world, phones matter. In this essay I will explain why. Phones help.")
    assert r.weak_openings == ["in this essay i will", "in today's world"]
    late = "Phones matter.\n\nThey help students.\n\nIn today's world, that is normal."
    assert analyze(late).weak_openings == []


def test_conclusion_that_repeats_the_introduction():
    intro = "Phones help students learn faster in class every single day of the week."
    text = f"{intro}\n\nThey give quick access to notes and videos.\n\nIn conclusion, {intro.lower()}"
    assert analyze(text).ending_issues == ["repeats-intro"]


def test_conclusion_with_new_evidence():
    text = "Phones help.\n\nThey give access to notes.\n\nOverall, 60% of students agree (Smith, 2020)."
    assert analyze(text).ending_issues == ["new-evidence"]
    assert analyze("Too short to have a conclusion (Smith, 2020).").ending_issues == []


def test_duration():
    assert duration(0, 238) == "under 1 min"
    assert duration(100, 238) == "under 1 min"
    assert duration(1000, 238) == "4 min"
    assert duration(1300, 130) == "10 min"
