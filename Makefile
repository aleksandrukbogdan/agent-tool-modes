.PHONY: test eval check long

test:
	pytest -q

eval:
	python -m lab.eval --split dev

check:
	python -m lab.eval --split check

long:
	python -m lab.eval --split long
