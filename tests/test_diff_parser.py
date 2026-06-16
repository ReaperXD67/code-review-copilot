import unittest

from app.utils.diff_parser import annotate_diff


class DiffParserTests(unittest.TestCase):
    def test_annotates_context_and_added_lines_with_new_file_numbers(self):
        raw_diff = "\n".join(
            [
                "diff --git a/example.py b/example.py",
                "--- a/example.py",
                "+++ b/example.py",
                "@@ -1,3 +10,4 @@",
                " existing = True",
                "+created = True",
                "-deleted = True",
                "+also_created = True",
            ]
        )

        annotated = annotate_diff(raw_diff)

        self.assertIn("[10]  existing = True", annotated)
        self.assertIn("[11] +created = True", annotated)
        self.assertIn("-deleted = True", annotated)
        self.assertIn("[12] +also_created = True", annotated)

    def test_handles_single_line_hunk_headers(self):
        raw_diff = "\n".join(
            [
                "diff --git a/new.py b/new.py",
                "--- /dev/null",
                "+++ b/new.py",
                "@@ -0,0 +1 @@",
                "+print('hello')",
            ]
        )

        annotated = annotate_diff(raw_diff)

        self.assertIn("[1] +print('hello')", annotated)


if __name__ == "__main__":
    unittest.main()
