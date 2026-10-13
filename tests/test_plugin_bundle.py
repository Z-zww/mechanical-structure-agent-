import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginBundleTests(unittest.TestCase):
    def test_plugin_bundle_tools_match_project_tools(self):
        project_tools = ROOT / "tools"
        bundled_tools = ROOT / "agh-plugin" / "tools"
        expected = {path.name for path in project_tools.glob("*.py")}
        actual = {path.name for path in bundled_tools.glob("*.py")}
        self.assertEqual(actual, expected)
        for name in sorted(expected):
            with self.subTest(tool=name):
                self.assertEqual(
                    (project_tools / name).read_bytes(),
                    (bundled_tools / name).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
