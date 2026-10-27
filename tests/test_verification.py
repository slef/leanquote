import unittest

from tex_support import TexTestCase
from export_support import export_files


class VerificationTests(TexTestCase):
    def test_filename_macros_preserve_strict_verification(self):
        code = "def value : Nat := 1\n"
        files = {"source directory/Current.lean": code}
        files.update(export_files(code))
        files.update({"project/" + path: text for path, text in export_files(code).items()})
        snippets, output = self.compile_tex(files, r"""
\leanquote[file=\SelectedFile,olean=\CompiledFile,verify=true]{value}
\leanquote[file=\SelectedExport,source=\CurrentSource,olean=\CompiledFile,verify=true]{value}
\leanquote[file=\CurrentSource,olean=\CompiledFile,verify=true]{value}
\leanquote[file=\SelectedExport,root=\SourceRoot,verify=true]{value}
\leanquote[project=\SourceRoot,file=\SelectedFile,verify=true]{value}
""", preamble=r"""
\def\SelectedFile{\SelectedModule.lean}
\def\SelectedModule{A}
\def\SelectedExport{A.leanquote}
\def\CompiledFile{A.olean}
\def\CurrentSource{source directory/Current.lean}
\def\SourceRoot{project/}
""")
        self.assertEqual(snippets, [code.strip()] * 5)
        self.assertNotIn("LEANQUOTE-BADGE:", output)

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
            r"\leanquotesetup{file=A.lean,keywordstyle={}}",
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
