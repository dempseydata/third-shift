"""`python -m unittest` runs the suite's tests on threads: each test spends its time waiting on
the subprocesses it drives, and each has its own folders (ADR 0007)."""
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor


class Threaded(unittest.TestSuite):
    def run(self, result, debug=False):
        lock = threading.Lock()

        class Locked:  # TestResult is not thread-safe; every call to it takes the lock
            def __getattr__(self, name):
                attr = getattr(result, name)
                if not callable(attr):
                    return attr

                def call(*args, **kwargs):
                    with lock:
                        return attr(*args, **kwargs)
                return call

        def flat(suite):
            for t in suite:
                yield from flat(t) if isinstance(t, unittest.TestSuite) else (t,)

        with ThreadPoolExecutor(os.cpu_count()) as pool:
            list(pool.map(lambda test: test(Locked()), flat(self)))
        return result


def load_tests(loader, tests, pattern):
    tests.addTests(loader.discover(os.path.dirname(__file__), pattern or "test*.py"))
    return Threaded(tests)
