"""Guard the template against `cwhip-pkg new` renaming, which rewrites text only."""

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TemplateRenameTests(unittest.TestCase):
    def test_no_tracked_path_contains_hello(self):
        # cwhip-pkg replaces `hello` in CMakeLists.txt and Markdown but never
        # renames files, so such a path would dangle after a rename.
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True,
            capture_output=True, text=True).stdout.splitlines()
        self.assertEqual(
            [path for path in tracked if "hello" in path.lower()], [])

    def test_cmake_referenced_scripts_exist(self):
        text = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        scripts = re.findall(r"\$\{PROJECT_SOURCE_DIR\}/(tests/[\w.-]+)", text)
        self.assertTrue(scripts)
        for script in scripts:
            self.assertTrue((ROOT / script).is_file(), script)


if __name__ == "__main__":
    unittest.main()
