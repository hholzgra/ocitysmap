PYTHON   = python
STAMPDIR = tests/.stamps

-include .deps.mk

.PHONY: clean
.SILENT: clean

.PHONY: lint
lint:
	flake8 | sort -k2 -k1

# clean up python compile cache files
clean::
	# clean Python precompile cache directores
	find . -name __pycache__ | xargs rm -rf

# generate dependencies for tests to run
.PHONY: depend
depend: .deps.mk

.deps.mk:
	$(PYTHON) scripts/make_test_deps.py > .deps.mk

clean::
	# clean "make depend" results
	rm -f .deps.mk

#  rununit tests
.PHONY: test
test: .deps.mk $(ALL_STAMPS)

clean::
	# clean "make test" stamp files
	find . -name .stamps | xargs rm -rf
