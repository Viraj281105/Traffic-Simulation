"""Scenario suites (V1.7, ``/api/suites``): named groups of runs, filled by
batch experiments that sweep a scenario's demand over several seeds.

Suites are private to their creator; admins see every suite, including
legacy ones stored before suites had an owner. Another user's suite answers
404, exactly like a missing one (tests/api/test_suite_privacy.py).
"""
