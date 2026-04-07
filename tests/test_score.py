from lab.score import match_answer


def test_answer_marker_and_spaced_integer():
    assert match_answer("ANSWER: 180000", 180000)
    assert match_answer("Рассуждение\nОтвет: 180 000 руб.", 180000)
    assert match_answer("ANSWER: 179999", 180000) is False


def test_string_fold_and_exactness():
    assert match_answer("ANSWER: Москва", "Москва")
    assert match_answer("ANSWER: малый", "малый")
    assert match_answer("Иванова работает в Москве", "Москва") is False
    assert match_answer("ANSWER: нет", "нет")
