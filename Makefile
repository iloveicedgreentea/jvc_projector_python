.PHONY: test dev_install

dev_install:
	pip3 install -r requirements-test.txt
test:
	python -m unittest discover -s tests