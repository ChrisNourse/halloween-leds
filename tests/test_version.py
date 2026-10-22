import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("project_version_tool", ROOT / "scripts/version.py")
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("package.json", "package-lock.json", "README.md", "STATUS.md",
                     "docs/build-guide/README.md", "docs/build-guide/provenance.json", "docs/releases/v0.9.0.md"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_semantic_increments_reset_lower_components(self):
        for amount, expected in (("patch", "0.9.3"), ("minor", "0.10.0"), ("major", "1.0.0")):
            self.assertEqual(version.bumped_version("0.9.2", amount), expected)
        for invalid in ("v0.9.2", "0.9", "0.09.2", "0.9.2;echo", "-1.0.0"):
            with self.assertRaises(ValueError):
                version.validate_version(invalid)

    def test_sync_updates_current_versions_preserving_history_and_dependencies(self):
        historical = (self.root / "docs/releases/v0.9.0.md").read_bytes()
        package = json.loads((self.root / "package-lock.json").read_text())
        dependencies = {k: v for k, v in package["packages"].items() if k}
        with (self.root / "README.md").open("a") as stream:
            stream.write("\nHistorical release: v0.9.0. Qualification target: v1.0.0.\n")
        version.synchronize_metadata(self.root, "0.9.3")
        self.assertEqual(version.project_version(self.root), "0.9.3")
        self.assertEqual(version.metadata_errors(self.root), [])
        self.assertIn("**v0.9.3 — experimental.", (self.root / "STATUS.md").read_text())
        self.assertIn("badge/v0.9.3-experimental", (self.root / "README.md").read_text())
        self.assertIn("Historical release: v0.9.0. Qualification target: v1.0.0.", (self.root / "README.md").read_text())
        self.assertEqual((self.root / "docs/releases/v0.9.0.md").read_bytes(), historical)
        updated = json.loads((self.root / "package-lock.json").read_text())
        self.assertEqual({k: v for k, v in updated["packages"].items() if k}, dependencies)

    def test_check_rejects_independently_stale_current_references(self):
        for name in ("README.md", "STATUS.md", "docs/build-guide/README.md",
                     "package-lock.json", "docs/build-guide/provenance.json"):
            with self.subTest(file=name):
                version.synchronize_metadata(self.root, "0.9.3")
                path = self.root / name
                path.write_text(path.read_text().replace("0.9.3", "0.9.2", 1))
                self.assertTrue(any(name in error for error in version.metadata_errors(self.root)))

    def test_changed_document_layout_fails_before_writing_any_files(self):
        path = self.root / "README.md"
        path.write_text(path.read_text().replace("current project version is", "project version"))
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "README.md"):
            version.synchronize_metadata(self.root, "0.9.3")
        self.assertEqual({p: p.read_bytes() for p in before}, before)
