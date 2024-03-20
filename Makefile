.PHONY: test dev_install build upload

dev_install:
	python3 -m venv .venv
	. .venv/bin/activate && \
	pip3 install -r requirements-test.txt
test:
	python -m unittest tests/test_coordinator.py

upload: build
	twine upload dist/*

build:
	rm -rf dist/*
	python3 -m build