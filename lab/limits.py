# Потолок ReAct и конвейера — как в прогоне 44 задач.
# План поднят после длинного среза: 8 вызовов и 4 шага не вмещали планировщик,
# повторный план и сборку ответа. Старые числа записаны в reports/dev.json.

REACT_STEPS = 8
PLAN_MODEL_CALLS = 20
PLAN_MAX_STEPS = 6
PLAN_INNER = 2
WORKFLOW_MODEL_CALLS = 5
