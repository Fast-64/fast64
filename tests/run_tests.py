"""Run every test module next to this file.

    python tests/run_tests.py

These are the tests that do not need Blender: each module is a plain script whose main()
returns nonzero on failure. Exits nonzero if any module fails.
"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    failures = []
    for filename in sorted(os.listdir(HERE)):
        if not filename.startswith("test_") or not filename.endswith(".py"):
            continue
        print(f"== {filename}")
        namespace = runpy.run_path(os.path.join(HERE, filename), run_name="run_tests")
        if namespace["main"]() != 0:
            failures.append(filename)

    if failures:
        print(f"\nfailed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
