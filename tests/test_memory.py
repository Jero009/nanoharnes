import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memory import memory as store
import memory


class MemoryTests(unittest.TestCase):
    def test_package_exports_memory_functions(self):
        for name in ("get_memory", "list_memory", "create_memory", "update_memory",
                     "delete_memory", "compact_memory_if_needed"):
            self.assertIs(getattr(memory, name), getattr(store, name))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "memories.json"
        memory_path = patch.object(store, "MEMORY_FILE", self.path)
        memory_path.start()
        self.addCleanup(memory_path.stop)

    def seed(self, content):
        self.path.write_text(content, encoding="utf-8")

    def test_missing_file_and_missing_key(self):
        self.assertEqual(store.list_memory(), {})
        self.assertIsNone(store.get_memory("editor"))
        self.assertFalse(self.path.exists())
        self.seed('{"editor": "VS Code"}')
        self.assertIsNone(store.get_memory("other"))
        self.assertEqual(store.get_memory("editor"), "VS Code")

    def test_invalid_json_or_shape_is_not_silently_reset(self):
        for content in ("{bad", "[]", '{"editor": 123}', "null"):
            with self.subTest(content=content):
                self.seed(content)
                with self.assertRaises(ValueError):
                    store.list_memory()
                with self.assertRaises(ValueError):
                    store.create_memory("new", "value", approve=lambda _: True)
                self.assertEqual(self.path.read_text(encoding="utf-8"), content)

    def test_invalid_utf8_and_oversized_file_fail(self):
        self.path.write_bytes(b"\xff")
        with self.assertRaises(ValueError):
            store.list_memory()
        self.seed(json.dumps({"large": "a" * 100_000}))
        with self.assertRaises(ValueError):
            store.list_memory()

    def test_create_without_approval_and_does_not_overwrite(self):
        self.assertIn("created", store.create_memory("editor", "VS Code").lower())
        self.assertEqual(store.list_memory(), {"editor": "VS Code"})
        self.assertIn("already exists", store.create_memory("editor", "Vim"))
        self.assertEqual(store.get_memory("editor"), "VS Code")

    def test_update_requires_existing_key_but_not_approval(self):
        self.assertIn("not found", store.update_memory("editor", "Vim"))
        store.create_memory("editor", "VS Code")
        requests = []
        self.assertIn("updated", store.update_memory("editor", "Vim", approve=lambda text: requests.append(text) or False).lower())
        self.assertEqual(requests, [])
        self.assertEqual(store.get_memory("editor"), "Vim")

    def test_delete_requires_existing_key_and_approval(self):
        self.assertIn("not found", store.delete_memory("editor", approve=lambda _: True))
        store.create_memory("editor", "VS Code", approve=lambda _: True)
        self.assertIn("denied", store.delete_memory("editor").lower())
        self.assertEqual(store.get_memory("editor"), "VS Code")
        self.assertIn("deleted", store.delete_memory("editor", approve=lambda _: True).lower())
        self.assertEqual(store.list_memory(), {})

    def test_delete_approval_failure_defaults_to_denial(self):
        def broken(_):
            raise RuntimeError("dialog closed")

        store.create_memory("editor", "VS Code")
        self.assertIn("denied", store.delete_memory("editor", approve=broken).lower())
        self.assertEqual(store.get_memory("editor"), "VS Code")

    def test_rejects_blank_keys_and_values(self):
        with self.assertRaises(ValueError):
            store.get_memory("  ")
        with self.assertRaises(ValueError):
            store.create_memory(" ", "value", approve=lambda _: True)
        with self.assertRaises(ValueError):
            store.create_memory("key", " ", approve=lambda _: True)
        with self.assertRaises(ValueError):
            store.update_memory("key", " ", approve=lambda _: True)
        with self.assertRaises(ValueError):
            store.delete_memory(" ", approve=lambda _: True)
        self.assertFalse(self.path.exists())

    def test_write_size_limit_preserves_existing_file(self):
        self.seed('{"editor": "VS Code"}')
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            store.create_memory("large", "x" * 500_000, approve=lambda _: True)
        self.assertEqual(self.path.read_bytes(), original)

    def model(self, keep):
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps({"keep": keep})))])
        fake = SimpleNamespace(
            client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
            get_model_name=lambda: "same-model",
        )
        return patch.dict(sys.modules, {"config.connection": fake}), calls

    def test_compaction_only_when_oversized_and_approved(self):
        with patch.object(store, "MAX_MEMORY_BYTES", 80):
            fake, calls = self.model(["important"])
            with fake:
                self.assertFalse(store.compact_memory_if_needed(approve=lambda _: True))
                self.assertEqual(calls, [])
                self.seed(json.dumps({"important": "A" * 35, "old": "B" * 35}))
                approvals = []
                def approve(description):
                    approvals.append(description)
                    return True
                self.assertTrue(store.compact_memory_if_needed(approve=approve))
            self.assertEqual(calls[0]["model"], "same-model")
            self.assertIn("old", approvals[0])
            self.assertEqual(store.list_memory(), {"important": "A" * 35})
            backups = list(self.path.parent.glob("memories-backup-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text())["old"], "B" * 35)

    def test_compaction_denial_and_invalid_proposal_do_not_write(self):
        with patch.object(store, "MAX_MEMORY_BYTES", 80):
            self.seed(json.dumps({"important": "A" * 35, "old": "B" * 35}))
            original = self.path.read_bytes()
            for keep, approve in [(["important"], lambda _: False),
                                  (["invented"], lambda _: True),
                                  (["important", "important"], lambda _: True),
                                  ([123], lambda _: True),
                                  ([], lambda _: True),
                                  (["important", "old"], lambda _: True)]:
                fake, _ = self.model(keep)
                with fake, self.assertRaises(ValueError):
                    store.compact_memory_if_needed(approve=approve)
                self.assertEqual(self.path.read_bytes(), original)
            self.assertEqual(list(self.path.parent.glob("memories-backup-*.json")), [])

    def test_missing_approval_does_not_contact_model(self):
        with patch.object(store, "MAX_MEMORY_BYTES", 80):
            self.seed(json.dumps({"important": "A" * 35, "old": "B" * 35}))
            original = self.path.read_bytes()
            fake, calls = self.model(["important"])
            with fake, self.assertRaises(ValueError):
                store.compact_memory_if_needed()
            self.assertEqual(calls, [])
            self.assertEqual(self.path.read_bytes(), original)

    def test_new_fact_is_protected_during_automatic_compaction(self):
        with patch.object(store, "MAX_MEMORY_BYTES", 80):
            self.seed(json.dumps({"old": "B" * 35}))
            original = self.path.read_bytes()
            fake, calls = self.model(["old"])
            with fake, self.assertRaises(ValueError):
                store.create_memory("new", "A" * 35, approve=lambda _: True)
            self.assertEqual(self.path.read_bytes(), original)
            fake, calls = self.model(["new"])
            with fake:
                store.create_memory("new", "A" * 35, approve=lambda _: True, model_name="active-model")
            self.assertEqual(calls[0]["model"], "active-model")
            self.assertEqual(store.list_memory(), {"new": "A" * 35})

    def test_automatic_write_does_not_delete_facts_without_compaction_approval(self):
        with patch.object(store, "MAX_MEMORY_BYTES", 80):
            self.seed(json.dumps({"old": "B" * 35}))
            original = self.path.read_bytes()
            fake, calls = self.model(["new"])
            with fake, self.assertRaises(ValueError):
                store.create_memory("new", "A" * 35)
            self.assertEqual(calls, [])
            self.assertEqual(self.path.read_bytes(), original)

            with fake, self.assertRaisesRegex(ValueError, "compaction denied"):
                store.create_memory("new", "A" * 35, approve=lambda _: False)
            self.assertEqual(self.path.read_bytes(), original)

    def test_failed_atomic_replace_preserves_existing_file(self):
        self.seed('{"editor": "VS Code"}')
        original = self.path.read_bytes()
        with patch.object(store.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                store.update_memory("editor", "Vim", approve=lambda _: True)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(Path(self.temp.name).glob(".memory-*")), [])


if __name__ == "__main__":
    unittest.main()
