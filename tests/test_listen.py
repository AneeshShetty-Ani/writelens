from ui.listen import MAX_HEIGHT, listen_html, player_height


def test_player_height_fits_the_text():
    assert player_height(["Short."]) < player_height(["A longer sentence. " * 8])
    assert player_height(["Very long text. " * 500]) == MAX_HEIGHT


def test_listen_page_has_sentences_and_controls():
    page = listen_html(["Hello there.", "Second one."])
    assert '["Hello there.", "Second one."]' in page
    assert page.count('<span class="s">') == 2
    assert 'id="play"' in page and "speechSynthesis" in page


def test_listen_escapes_user_text():
    page = listen_html(["</script><script>alert(1)</script>", "<b>bold</b>"])
    assert "</script><script>alert(1)" not in page
    assert "&lt;b&gt;bold&lt;/b&gt;" in page
