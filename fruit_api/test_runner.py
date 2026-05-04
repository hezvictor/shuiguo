import unittest

from django.test.runner import DiscoverRunner


class CompatibleTextTestRunner(unittest.TextTestRunner):
    def __init__(self, *args, durations=None, **kwargs):
        super().__init__(*args, **kwargs)


class CompatibleDiscoverRunner(DiscoverRunner):
    """Project-local test runner hook used by settings."""

    test_runner = CompatibleTextTestRunner
