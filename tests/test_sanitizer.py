from src.sanitizer import remove_dashes, has_dashes, find_repeated_words


def test_remove_em_and_en_dashes():
    assert remove_dashes("fast—paced and data–driven") == "fast paced and data driven"


def test_remove_hyphen_between_words():
    assert remove_dashes("well-organized team-player") == "well organized team player"


def test_number_range_becomes_to():
    assert remove_dashes("managed 5-10 people") == "managed 5 to 10 people"


def test_year_range_becomes_to():
    assert remove_dashes("Acme Corp 2019-2024") == "Acme Corp 2019 to 2024"


def test_year_to_present_becomes_to():
    assert remove_dashes("DataCorp 2021-Present") == "DataCorp 2021 to Present"


def test_phone_number_dashes_do_not_become_to():
    assert remove_dashes("555-9876") == "555 9876"
    assert remove_dashes("call 555-123-4567 today") == "call 555 123 4567 today"


def test_has_dashes_detects_all_kinds():
    assert has_dashes("a-b") is True
    assert has_dashes("a–b") is True
    assert has_dashes("a—b") is True
    assert has_dashes("clean text") is False


def test_find_repeated_words_flags_overuse():
    text = "led led led led team using tools"
    assert "led" in find_repeated_words(text, protected=set(), threshold=4)


def test_find_repeated_words_ignores_protected_keywords():
    text = "python python python python python"
    assert find_repeated_words(text, protected={"python"}, threshold=4) == []


def test_find_repeated_words_ignores_stopwords():
    text = "the the the the the the report"
    assert find_repeated_words(text, protected=set(), threshold=4) == []
