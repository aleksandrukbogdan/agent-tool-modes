from lab.tasks import TASKS


def test_frozen_slice_has_44_tasks():
    assert len(TASKS) == 44
    assert len({task.id for task in TASKS}) == 44
    counts = {}
    for task in TASKS:
        counts[task.family] = counts.get(task.family, 0) + 1
    assert counts == {
        "calc": 8,
        "lookup": 8,
        "compose": 8,
        "policy": 6,
        "branch": 4,
        "recover": 6,
        "open": 4,
    }


def test_hand_checked_golds():
    gold = {task.id: task.gold for task in TASKS}
    assert gold["c01"] == 43200
    assert gold["a01"] == 2160000
    assert gold["a04"] == 5740000
    assert gold["a05"] == 12
    assert gold["a07"] == 2688
    assert gold["p02"] == 31
    assert gold["p04"] == 13500
    assert gold["p06"] == 243000
    assert gold["b01"] == 97849
    assert gold["b02"] == 31
    assert gold["b03"] == "малый"
    assert gold["b04"] == "да"
    assert gold["l01"] == "Москва"
    assert gold["l07"] == "2021-07-19"
    assert gold["r01"] == "Москва"
    assert gold["r04"] == -1
    assert gold["r05"] == "нет"
    assert gold["r06"] == 200000
    assert gold["o01"] == 370000
    assert gold["o02"] == 2400
    assert gold["o03"] == 63000
    assert gold["o04"] == 97849
