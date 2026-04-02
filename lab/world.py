# Замороженный мир бенчмарка. Золотые ответы считаются из этих таблиц.

AS_OF = "2026-10-11"

FX = {"RUB": 1, "USD": 93, "EUR": 100, "CNY": 13}

EMPLOYEES = [
    {"name": "Иванова Анна", "department": "финансы", "salary": 180000, "city": "Москва", "start": "2019-03-01", "manager": "Петров Игорь"},
    {"name": "Петров Игорь", "department": "финансы", "salary": 250000, "city": "Москва", "start": "2016-01-15", "manager": "Соколова Мария"},
    {"name": "Соколова Мария", "department": "управление", "salary": 320000, "city": "Москва", "start": "2014-06-01", "manager": None},
    {"name": "Смирнов Павел", "department": "разработка", "salary": 210000, "city": "Казань", "start": "2021-09-01", "manager": "Орлов Денис"},
    {"name": "Смирнова Ольга", "department": "разработка", "salary": 190000, "city": "Казань", "start": "2022-02-14", "manager": "Орлов Денис"},
    {"name": "Орлов Денис", "department": "разработка", "salary": 280000, "city": "Казань", "start": "2018-11-20", "manager": "Соколова Мария"},
    {"name": "Кузнецов Илья", "department": "продажи", "salary": 140000, "city": "Новосибирск", "start": "2020-05-05", "manager": "Волкова Елена"},
    {"name": "Волкова Елена", "department": "продажи", "salary": 230000, "city": "Новосибирск", "start": "2017-08-30", "manager": "Соколова Мария"},
    {"name": "Иванов Сергей", "department": "разработка", "salary": 160000, "city": "Москва", "start": "2023-01-10", "manager": "Орлов Денис"},
    {"name": "Морозов Артём", "department": "поддержка", "salary": 120000, "city": "Казань", "start": "2024-04-01", "manager": "Орлов Денис"},
    {"name": "Новикова Дарья", "department": "финансы", "salary": 150000, "city": "Москва", "start": "2020-12-01", "manager": "Петров Игорь"},
    {"name": "Белов Кирилл", "department": "продажи", "salary": 135000, "city": "Москва", "start": "2021-07-19", "manager": "Волкова Елена"},
]

DEPARTMENTS = [
    {"name": "финансы", "budget": 4200000, "head": "Петров Игорь", "city": "Москва"},
    {"name": "разработка", "budget": 9100000, "head": "Орлов Денис", "city": "Казань"},
    {"name": "продажи", "budget": 3800000, "head": "Волкова Елена", "city": "Новосибирск"},
    {"name": "поддержка", "budget": 1500000, "head": "Орлов Денис", "city": "Казань"},
    {"name": "управление", "budget": 2100000, "head": "Соколова Мария", "city": "Москва"},
]

POLICIES = [
    {
        "id": "vacation",
        "text": "Базовый отпуск 28 календарных дней. Если год начала работы 2018 или раньше, отпуск 31 день.",
    },
    {
        "id": "bonus",
        "text": "Годовая премия: 15 процентов годовой зарплаты в отделе продажи, 10 процентов в остальных отделах.",
    },
    {
        "id": "perdiem",
        "text": "Суточные за день: Москва 1500, Казань 1200, Новосибирск 1300, другой город 1000. Если командировка длиннее 7 дней, сумма суточных умножается на 9 и делится нацело на 10.",
    },
]

PER_DIEM = {"москва": 1500, "казань": 1200, "новосибирск": 1300}


def fold(text):
    return " ".join(text.casefold().replace("ё", "е").split())


def parse_date(text):
    parts = text.split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
    except ValueError:
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return None
    return year, month, day


def years_between(start, end):
    a = parse_date(start)
    b = parse_date(end)
    if a is None or b is None:
        return None
    years = b[0] - a[0]
    if (b[1], b[2]) < (a[1], a[2]):
        years -= 1
    return years


def start_year(employee):
    return int(employee["start"][:4])


def public_employee(employee):
    return {
        "name": employee["name"],
        "department": employee["department"],
        "salary": employee["salary"],
        "city": employee["city"],
        "start": employee["start"],
        "start_year": start_year(employee),
        "manager": employee["manager"],
    }


def per_diem(city, days):
    rate = PER_DIEM.get(fold(city), 1000)
    total = rate * days
    if days > 7:
        total = total * 9 // 10
    return total


def bonus_percent(department):
    return 15 if fold(department) == "продажи" else 10


def annual_bonus(salary, department):
    return salary * 12 * bonus_percent(department) // 100


def convert_amount(amount, src, dst):
    src = src.upper()
    dst = dst.upper()
    if src not in FX or dst not in FX:
        return None
    return amount * FX[src] // FX[dst]


def find_employee(name):
    key = fold(name)
    for employee in EMPLOYEES:
        if fold(employee["name"]) == key:
            return employee
    return None


def find_department(name):
    key = fold(name)
    for department in DEPARTMENTS:
        if fold(department["name"]) == key:
            return department
    return None
