.PHONY: test dev_install build upload

dev_install:
	pip3 install -r requirements-test.txt
test:
	python -m unittest discover -s tests

upload: build
	twine upload dist/*

build:
	rm -rf dist/*
	python3 -m build