from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid
from unittest import skipUnless
from django.db import connection, close_old_connections
from django.test import TransactionTestCase
from .tests import SchedulingTests
from .services import create_draft, save_entries, ScheduleConflict


@skipUnless(
    connection.vendor == "mysql",
    "Requires a dedicated MySQL test database and real row locks.",
)
class MySQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        SchedulingTests.setUp(self)

    def entry(self, **overrides):
        return SchedulingTests.entry(self, **overrides)

    def test_parallel_sections_cannot_reserve_same_faculty_and_room(self):
        second = create_draft(self.admin, self.section2.pk, uuid.uuid4())
        barrier = Barrier(2)

        def attempt(pk):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                save_entries(self.admin, pk, 0, [self.entry()])
                return "saved"
            except ScheduleConflict:
                return "conflict"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [self.table.pk, second.pk]))
        self.assertCountEqual(results, ["saved", "conflict"])
