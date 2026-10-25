import unittest

from tex_support import TexTestCase
from export_support import export_files


class VerificationTests(TexTestCase):
    def test_compiled_file_override_is_not_cached_by_source(self):
        _, output = self.compile_tex(
            {"A.lean": "def value : Nat := 1\n", "valid.olean": "compiled"},
            r"""
\leanquote[file=A.lean,olean=valid.olean,verify=true]{value}
\leanquote[file=A.lean,olean=missing.olean,verify=true]{value}
""",
        )
        self.assertEqual(output.count("LEANQUOTE-BADGE:UNVERIFIED"), 1)
        self.assertIn("missing.olean", output)

    def test_stricter_verification_is_not_silenced_by_cache(self):
        _, output = self.compile_tex(
            {"A.lean": "def value : Nat := 1\n"},
            r"""
\leanquote[file=A.lean,verify=auto]{value}
\leanquote[file=A.lean,verify=true]{value}
""",
        )
        self.assertEqual(output.count("LEANQUOTE-BADGE:UNVERIFIED"), 1)
        self.assertIn("Package leanquote Warning", output)

    def test_axioms_are_complete_names(self):
        for axioms, badge in [
            ("propext Classical.choice Quot.sound", None),
            ("propextpropext", "EXTRA AXIOMS"),
            ("sorryAx.sorryAx", "EXTRA AXIOMS"),
            ("sorryAx", "USES SORRY"),
        ]:
            with self.subTest(axioms=axioms):
                _, output = self.compile_tex(
                    export_files("theorem bad : True := by trivial\n", name="bad", axioms=axioms),
                    r"\leanquote[file=A.leanquote]{bad}",
                )
                marks = [line for line in output.splitlines() if line.startswith("LEANQUOTE-BADGE:")]
                self.assertEqual(marks, [] if badge is None else ["LEANQUOTE-BADGE:" + badge])

    def test_empty_and_bare_listings_options(self):
        for setup in [
            r"\leanquotesetup{keywordstyle={}}",
            r"\leanquotefile[keywordstyle={}]{A.lean}",
            "",
        ]:
            with self.subTest(setup=setup):
                snippets, _ = self.compile_tex(
                    {"A.lean": "def value : Nat := 1\n"},
                    r"\leanquote[file=A.lean,breaklines,keywordstyle={}]{value}",
                    preamble=setup,
                )
                self.assertEqual(snippets, ["def value : Nat := 1"])

    def test_string_literals_with_default_font_encoding(self):
        snippets, _ = self.compile_tex(
            {"A.lean": 'def greeting : String := "hello"\n'},
            r"\leanquote[file=A.lean]{greeting}", fontenc=False,
        )
        self.assertEqual(snippets, ['def greeting : String := "hello"'])


if __name__ == "__main__":
    unittest.main()
