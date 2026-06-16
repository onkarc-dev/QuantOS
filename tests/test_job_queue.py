"""Tests for job queue abstraction."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.services.job_queue import (
    InMemoryJobQueue, ThreadedJobQueue, QueueJob, JobStatus
)


class TestInMemoryQueue(unittest.TestCase):
    def setUp(self):
        self.queue = InMemoryJobQueue()

    def test_enqueue_creates_job(self):
        job = self.queue.enqueue("backtest", {"symbol": "BTCUSDT"})
        self.assertIsNotNone(job.id)
        self.assertEqual(job.status, JobStatus.queued)
        self.assertEqual(job.kind, "backtest")

    def test_get_returns_job(self):
        job = self.queue.enqueue("backtest", {"symbol": "BTCUSDT"})
        retrieved = self.queue.get(job.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, job.id)

    def test_get_nonexistent_returns_none(self):
        result = self.queue.get("no-such-id")
        self.assertIsNone(result)

    def test_list_returns_all_jobs(self):
        self.queue.enqueue("backtest", {})
        self.queue.enqueue("backtest", {})
        self.queue.enqueue("paper_trade", {})
        all_jobs = self.queue.list()
        self.assertEqual(len(all_jobs), 3)

    def test_list_filters_by_kind(self):
        self.queue.enqueue("backtest", {})
        self.queue.enqueue("backtest", {})
        self.queue.enqueue("paper_trade", {})
        backtest_jobs = self.queue.list("backtest")
        self.assertEqual(len(backtest_jobs), 2)

    def test_run_executes_function(self):
        job = self.queue.enqueue("test", {})

        def dummy_fn(payload):
            return {"result": "success"}

        result_job = self.queue.run(job.id, dummy_fn)
        self.assertEqual(result_job.status, JobStatus.completed)
        self.assertEqual(result_job.result, {"result": "success"})

    def test_run_catches_exceptions(self):
        job = self.queue.enqueue("test", {})

        def failing_fn(payload):
            raise ValueError("Test error")

        result_job = self.queue.run(job.id, failing_fn)
        self.assertEqual(result_job.status, JobStatus.failed)
        self.assertIn("Test error", result_job.error)

    def test_cancel_queued_job_succeeds(self):
        job = self.queue.enqueue("test", {})
        success = self.queue.cancel(job.id)
        self.assertTrue(success)
        cancelled = self.queue.get(job.id)
        self.assertEqual(cancelled.status, JobStatus.cancelled)

    def test_cancel_completed_job_fails(self):
        job = self.queue.enqueue("test", {})
        self.queue.run(job.id, lambda p: {})
        success = self.queue.cancel(job.id)
        self.assertFalse(success)

    def test_stats_total(self):
        self.queue.enqueue("a", {})
        j2 = self.queue.enqueue("b", {})
        self.queue.run(j2.id, lambda p: {})
        stats = self.queue.stats()
        self.assertEqual(stats["total"], 2)

    def test_stats_completed_count(self):
        j = self.queue.enqueue("b", {})
        self.queue.run(j.id, lambda p: {})
        stats = self.queue.stats()
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["queued"], 0)

    def test_payload_stored(self):
        payload = {"symbol": "BTCUSDT", "timeframe": "1m"}
        job = self.queue.enqueue("backtest", payload)
        stored = self.queue.get(job.id)
        self.assertEqual(stored.payload["symbol"], "BTCUSDT")

    def test_run_sets_timestamps(self):
        job = self.queue.enqueue("test", {})
        result_job = self.queue.run(job.id, lambda p: {})
        self.assertNotEqual(result_job.completed_at, "")
        self.assertNotEqual(result_job.started_at, "")


class TestThreadedQueue(unittest.TestCase):
    def setUp(self):
        self.queue = ThreadedJobQueue()

    def test_enqueue_and_run_eventually_completes(self):
        """Job should complete in background thread."""
        import time

        def quick_fn(payload):
            return {"done": True}

        job = self.queue.enqueue_and_run("test", {}, quick_fn)
        # Job was submitted — ID should be valid
        self.assertIsNotNone(job.id)

        # Wait for background thread to complete
        deadline = time.time() + 2.0
        while time.time() < deadline:
            result = self.queue.get(job.id)
            if result and result.status in (JobStatus.completed, JobStatus.failed):
                break
            time.sleep(0.05)

        final = self.queue.get(job.id)
        self.assertEqual(final.status, JobStatus.completed)
        self.assertEqual(final.result, {"done": True})

    def test_threaded_queue_stats_shows_backend(self):
        stats = self.queue.stats()
        self.assertEqual(stats["backend"], "threaded")

    def test_threaded_queue_error_captured(self):
        """Exceptions in background worker should be captured."""
        import time

        def bad_fn(payload):
            raise RuntimeError("background failure")

        job = self.queue.enqueue_and_run("test", {}, bad_fn)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            result = self.queue.get(job.id)
            if result and result.status in (JobStatus.completed, JobStatus.failed):
                break
            time.sleep(0.05)

        final = self.queue.get(job.id)
        self.assertEqual(final.status, JobStatus.failed)
        self.assertIn("background failure", final.error)


if __name__ == "__main__":
    unittest.main()
