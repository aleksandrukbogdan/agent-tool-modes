from lab.tasks import Task
from lab.world import annual_bonus, convert_amount, find_department, find_employee, per_diem, years_between

AS_OF = "2026-10-11"


def build_long_tasks():
    belov = find_employee("Белов Кирилл")
    novikova = find_employee("Новикова Дарья")
    orlov = find_employee("Орлов Денис")
    anna = find_employee("Иванова Анна")
    boss = find_employee(anna["manager"])
    boss2 = find_employee(boss["manager"])
    boss_dept = find_department(boss2["department"])
    olga = find_employee("Смирнова Ольга")
    morozov = find_employee("Морозов Артём")
    volkova = find_employee("Волкова Елена")
    support = find_department("поддержка")
    head = find_employee(support["head"])
    bonus_gap = annual_bonus(belov["salary"], belov["department"]) - annual_bonus(
        novikova["salary"], novikova["department"]
    )
    volkova_days = years_between(volkova["start"], AS_OF)
    morozov_days = years_between(morozov["start"], AS_OF)
    return [
        Task(
            "d01",
            "chain",
            "На сколько годовая премия Белова Кирилла больше годовой премии Новиковой Дарьи, "
            "если разницу перевести в доллары США? Процент премии бери из политики. "
            "Годовая зарплата — месячная, умноженная на 12. Курс бери из инструмента валют, дробную часть отбрось.",
            convert_amount(bonus_gap, "RUB", "USD"),
        ),
        Task(
            "d02",
            "chain",
            "Какова годовая премия Орлова Дениса в долларах США? Процент премии бери из политики. "
            "Годовая зарплата — месячная, умноженная на 12. Курс бери из инструмента валют, дробную часть отбрось.",
            convert_amount(annual_bonus(orlov["salary"], orlov["department"]), "RUB", "USD"),
        ),
        Task(
            "d03",
            "chain",
            "Чему равен годовой бюджет отдела, в котором работает руководитель руководителя Ивановой Анны, "
            "в долларах США? Курс бери из инструмента валют, дробную часть отбрось.",
            convert_amount(boss_dept["budget"], "RUB", "USD"),
        ),
        Task(
            "d04",
            "chain",
            "Какова годовая зарплата сотрудницы с фамилией Смирнов в долларах США? "
            "Фамилия может совпасть у нескольких людей, нужна сотрудница. "
            "Годовая зарплата — месячная, умноженная на 12. Курс бери из инструмента валют, дробную часть отбрось.",
            convert_amount(olga["salary"] * 12, "RUB", "USD"),
        ),
        Task(
            "d05",
            "chain",
            "На сколько суточные Волковой Елены больше суточных Морозова Артёма, если длительность каждой "
            "командировки в днях равна числу полных лет работы этого сотрудника на дату 2026-10-11? "
            "Город бери из карточки сотрудника, ставку суточных — из политики.",
            per_diem(volkova["city"], volkova_days) - per_diem(morozov["city"], morozov_days),
        ),
        Task(
            "d06",
            "chain",
            "Какова месячная зарплата руководителя отдела «поддержка» в евро? "
            "Курс бери из инструмента валют, дробную часть отбрось.",
            convert_amount(head["salary"], "RUB", "EUR"),
        ),
    ]


LONG_TASKS = build_long_tasks()
LONG_BY_ID = {task.id: task for task in LONG_TASKS}
