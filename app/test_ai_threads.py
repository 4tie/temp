from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai.memory import threads


class ThreadStoreTests(unittest.TestCase):
    def test_thread_crud_and_context_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            threads_dir = base / "threads"
            conversations_dir = base / "conversations"

            with (
                patch.object(threads, "AI_THREADS_DIR", threads_dir),
                patch.object(threads, "AI_CONVERSATIONS_DIR", conversations_dir),
                patch.object(threads, "build_context_snapshot", return_value={"snapshot": True}),
            ):
                thread = threads.create_thread(goal_id="maximize_profit")
                thread_id = thread["thread_id"]

                self.assertTrue((threads_dir / f"{thread_id}.json").exists())
                self.assertEqual(thread.get("goal_id"), "maximize_profit")
                self.assertEqual(thread.get("context_snapshot"), {"snapshot": True})

                updated = threads.append_message(
                    thread_id=thread_id,
                    role="user",
                    content="hello",
                )
                self.assertEqual(len(updated.get("messages", [])), 1)

                loaded = threads.load_thread(thread_id)
                self.assertIsNotNone(loaded)
                self.assertEqual(len(loaded.get("messages", [])), 1)

                listed = threads.list_threads(limit=10)
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0].get("thread_id"), thread_id)

                deleted = threads.delete_thread(thread_id)
                self.assertTrue(deleted)
                self.assertIsNone(threads.load_thread(thread_id))


if __name__ == "__main__":
    unittest.main()
