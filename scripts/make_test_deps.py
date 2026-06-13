#!/usr/bin/env python3
"""Generate Makefile dependency rules for test stamp files.

Run from the project root:
    python scripts/make_test_deps.py > deps.mk

The output is intended to be included by the Makefile via '-include deps.mk'.
Each rule has the form:

    tests/.stamps/bar/.test_foo: tests/bar/test_foo.py ocitysmap/bar/foo.py ...

Dependencies are discovered by parsing each test file's import statements with
ast, then resolving each imported name to the file where it is actually defined
(via __module__).  This avoids pulling in unrelated transitive imports that
happen to be loaded by package __init__ files.
"""

import ast
import importlib
import importlib.util
import sys
from pathlib import Path

STAMPS_ROOT = Path('tests/.stamps')
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Ensure the project root is importable regardless of how this script is invoked.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def resolve_to_project_file(module_name):
    """Return the project-relative path for a module, or None if outside the project."""
    try:
        spec = importlib.util.find_spec(module_name)
    except (ModuleNotFoundError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    try:
        return str(Path(spec.origin).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return None  # stdlib or third-party


def project_deps(test_file):
    """Return sorted project-local files that test_file directly depends on."""
    source = test_file.read_text(encoding='utf-8')
    tree = ast.parse(source)
    deps = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Include the package/module being imported from
            p = resolve_to_project_file(node.module)
            if p:
                deps.add(p)

            # For each name, find the file where it is actually defined
            try:
                mod = importlib.import_module(node.module)
            except ImportError:
                continue
            for alias in node.names:
                obj = getattr(mod, alias.name, None)
                origin = getattr(obj, '__module__', None)
                if origin:
                    p = resolve_to_project_file(origin)
                    if p:
                        deps.add(p)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                p = resolve_to_project_file(alias.name)
                if p:
                    deps.add(p)

    return sorted(deps)


def module_name(test_file):
    """Convert a file path to a dotted module name relative to the project root."""
    rel = test_file.relative_to(PROJECT_ROOT)
    return '.'.join(rel.with_suffix('').parts)


def main():
    test_files = sorted(PROJECT_ROOT.glob('tests/**/test_*.py'))
    if not test_files:
        print('# no test files found', file=sys.stderr)
        sys.exit(1)

    stamps = []
    rules = []
    for test_file in test_files:
        rel_test = str(test_file.relative_to(PROJECT_ROOT))
        rel_dir  = test_file.relative_to(PROJECT_ROOT).parent
        stampdir = STAMPS_ROOT / rel_dir.relative_to('tests')
        stamp    = str(stampdir / f'.{test_file.stem}')
        deps = project_deps(test_file)
        all_deps = sorted(set([rel_test] + deps))
        stamps.append(stamp)
        rules.append((stamp, stampdir, all_deps, module_name(test_file)))

    print(f'ALL_STAMPS = {" ".join(stamps)}')
    print()
    for stamp, stampdir, all_deps, mod in rules:
        print(f'{stamp}: {" ".join(all_deps)}')
        print(f'\t@output=$$($(PYTHON) -m unittest {mod} 2>&1) && echo "OK: {mod}" || {{ echo "$$output"; exit 1; }}')
        print(f'\t@mkdir -p {stampdir}')
        print(f'\t@touch $@')
        print()


if __name__ == '__main__':
    main()
