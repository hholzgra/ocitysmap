PYTHON   = python
STAMPDIR = tests/.stamps

-include .deps.mk

.PHONY: clean
.SILENT: clean
clean::
	# clean Python precompile cache directores
	find . -name __pycache__ | xargs rm -rf

.PHONY: lint
lint:
	flake8 | sort -k2 -k1

.PHONY: test
test: $(ALL_STAMPS)
	@[ -n "$(ALL_STAMPS)" ] || { echo "No .deps.mk — run 'make depend' first"; exit 1; }

clean::
	# clean "make test" stamp files
	find . -name .stamps | xargs rm -rf

.PHONY: depend
depend:
	$(PYTHON) scripts/make_test_deps.py > .deps.mk

clean::
	# clean "make depend" results
	rm -f .deps.mk
