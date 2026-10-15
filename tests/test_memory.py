import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memory import memory as store


class MemoryTests(unittest.TestCase):
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

    def test_create_requires_approval_and_does_not_overwrite(self):
        self.assertIn("denied", store.create_memory("editor", "VS Code").lower())
        self.assertFalse(self.path.exists())
        self.assertIn("created", store.create_memory("editor", "VS Code", approve=lambda _: True).lower())
        self.assertEqual(store.list_memory(), {"editor": "VS Code"})
        self.assertIn("already exists", store.create_memory("editor", "Vim", approve=lambda _: True))
        self.assertEqual(store.get_memory("editor"), "VS Code")

    def test_update_requires_existing_key_and_approval(self):
        self.assertIn("not found", store.update_memory("editor", "Vim", approve=lambda _: True))
        store.create_memory("editor", "VS Code", approve=lambda _: True)
        requests = []
        self.assertIn("denied", store.update_memory("editor", "Vim", approve=lambda text: requests.append(text) or False).lower())
        self.assertIn("VS Code", requests[0])
        self.assertIn("Vim", requests[0])
        self.assertEqual(store.get_memory("editor"), "VS Code")
        self.assertIn("updated", store.update_memory("editor", "Vim", approve=lambda _: True).lower())
        self.assertEqual(store.get_memory("editor"), "Vim")

    def test_delete_requires_existing_key_and_approval(self):
        self.assertIn("not found", store.delete_memory("editor", approve=lambda _: True))
        store.create_memory("editor", "VS Code", approve=lambda _: True)
        self.assertIn("denied", store.delete_memory("editor").lower())
        self.assertEqual(store.get_memory("editor"), "VS Code")
        self.assertIn("deleted", store.delete_memory("editor", approve=lambda _: True).lower())
        self.assertEqual(store.list_memory(), {})

    def test_approval_failure_defaults_to_denial(self):
        def broken(_):
            raise RuntimeError("dialog closed")

        self.assertIn("denied", store.create_memory("editor", "VS Code", approve=broken).lower())
        self.assertFalse(self.path.exists())

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
            store.create_memory("large", "x" * 100_000, approve=lambda _: True)
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
