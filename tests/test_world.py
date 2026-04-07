from lab.world import annual_bonus, convert_amount, per_diem, years_between


def test_years_do_not_count_an_anniversary_that_has_not_arrived():
    assert years_between("2024-04-01", "2026-10-11") == 2
    assert years_between("2024-04-01", "2026-04-01") == 2
    assert years_between("2024-04-01", "2026-03-31") == 1


def test_per_diem_discount_after_seven_days():
    assert per_diem("Казань", 4) == 4800
    assert per_diem("Москва", 10) == 13500
    assert per_diem("Новосибирск", 7) == 9100


def test_money_and_bonus_are_integer():
    assert convert_amount(250000, "RUB", "USD") == 2688
    assert convert_amount(9100000, "RUB", "USD") == 97849
    assert convert_amount(100, "USD", "RUB") == 9300
    assert annual_bonus(135000, "продажи") == 243000
    assert annual_bonus(150000, "финансы") == 180000
