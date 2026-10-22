from nlp_checks import check


def test_passive_detected():
    r = check("The report was written by the team. We wrote the summary.")
    assert r.passive == ["The report was written by the team."]


def test_repeated_words_use_lemmas():
    r = check("The report is long. Reports matter. Each report helps.")
    assert ("report", 3) in r.repeated


def test_weak_verbs_skip_auxiliaries():
    r = check("We get results. The ball was thrown.")
    verbs = dict(r.weak_verbs)
    assert verbs.get("get") == 1
    assert "be" not in verbs


def test_filler_adverbs():
    r = check("It is really very good.")
    assert dict(r.adverbs) == {"really": 1, "very": 1}


def test_ly_adverbs_flagged_except_keep_list():
    r = check("She honestly and quickly finished. Only he left early.")
    adverbs = dict(r.adverbs)
    assert adverbs.get("honestly") == 1 and adverbs.get("quickly") == 1
    assert "only" not in adverbs and "early" not in adverbs


def test_pretty_only_flagged_as_adverb():
    assert "pretty" in dict(check("It was pretty good.").adverbs)
    assert "pretty" not in dict(check("She has a pretty garden.").adverbs)


def test_clean_text_has_no_findings():
    r = check("Cats chase mice.")
    assert not (r.passive or r.repeated or r.weak_verbs or r.adverbs)
