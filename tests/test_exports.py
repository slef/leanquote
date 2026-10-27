import unittest

from export_support import export_files, make_export
from tex_support import TexTestCase


class ExportTests(TexTestCase):
    def test_unrelated_sidecar_cannot_supply_fallback_artifact(self):
        bad = "theorem bad : False := by no_such_tactic\n"
        good = "def value : Nat := 1\n"
        for snapshot in [good, bad]:
            with self.subTest(matching_snapshot=snapshot == bad):
                files = {
                    "A.lean": good, "B.lean": bad,
                    "A.olean": "compiled", "A.trace": '{"depHash": "build-a"}',
                    ".lake/build/lib/lean/B.trace": "failed build",
                    "B.leanquote": make_export(snapshot, source_path="A.lean", olean="A.olean"),
                }
                snippets, output = self.compile_tex(
                    files, r"\leanquote[file=B.lean,verify=true,proof=false]{bad}",
                )
                self.assertEqual(snippets, ["theorem bad : False := ..."])
                self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)
                self.assertIn("does not identify B.lean", " ".join(output.split()))
                self.assertIn("last lake build of B.lean failed", " ".join(output.split()))

    def test_missing_source_identity_cannot_supply_fallback_artifact(self):
        files = export_files()
        files["A.leanquote"] = files["A.leanquote"].replace("@@source A.lean\n", "")
        _, output = self.compile_tex(files, r"\leanquote[file=A.lean,verify=true]{value}")
        self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)

    def test_stale_same_source_keeps_custom_artifact_path(self):
        current = "def value : Nat := 2\n"
        files = {
            "project/src/A.lean": current,
            "project/.lake/build/leanquote/src/A.leanquote": make_export(
                "def value : Nat := 1\n", source_path="src/./A.lean", olean="out/lib/A.olean",
            ),
            "project/out/lib/A.olean": "compiled",
            "project/out/lib/A.trace": '{"depHash": "build-a"}',
        }
        snippets, output = self.compile_tex(
            files, r"\leanquote[project=project/,file=src/A.lean,verify=true]{value}",
        )
        self.assertEqual(snippets, [current.strip()])
        self.assertIn("Reading project/src/A.lean directly", " ".join(output.split()))
        self.assertNotIn("LEANQUOTE-BADGE:", output)

    def test_explicit_export_with_missing_artifact_and_trace_is_unverified(self):
        files = export_files(axioms="sorryAx")
        del files["A.olean"]
        _, output = self.compile_tex(files, r"\leanquote[file=A.leanquote,verify=auto]{value}")
        self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)
        self.assertNotIn("LEANQUOTE-BADGE:USES SORRY", output)

    def test_export_name_components_match_source_lookup(self):
        code = "namespace A\ndef plain : Nat := 1\nend A\n"
        for name in ["plain", "A.plain", "_root_.A.plain", "A.«plain»", "«A».plain"]:
            with self.subTest(name=name):
                files = export_files(code, name="A.plain")
                files["A.leanquote"] = make_export("def plain : Nat := 1\n", source=code, name="A.plain")
                snippets, _ = self.compile_tex(files, r"\leanquote[file=A.leanquote]{" + name + "}")
                self.assertEqual(snippets, ["def plain : Nat := 1"])
        for name in ["_root_.plain", "Missing.plain", "«A.plain»"]:
            with self.subTest(name=name):
                self.compile_tex(files, r"\leanquote[file=A.leanquote]{" + name + "}", success=False)

    def test_imports_with_exports_preserve_declaration_verification(self):
        declaration = "theorem bad : True := by sorry\n"
        source = "import Init\n\n" + declaration
        files = export_files(source, name="bad", axioms="sorryAx")
        files["A.leanquote"] = make_export(
            declaration, source=source, name="bad", axioms="sorryAx",
        )
        snippets, output = self.compile_tex(files, r"""
\leanquote[imports,file=A.lean,verify=true]{bad}
\leanquote[imports,file=A.leanquote,verify=true]{bad}
\leanquote[imports,file=A.leanquote,verify=true]{}
""")
        self.assertEqual(snippets, [source.strip(), source.strip(), "import Init"])
        self.assertEqual(output.count("LEANQUOTE-BADGE:USES SORRY"), 2)
        self.assertNotIn("LEANQUOTE-BADGE:UNVERIFIED", output)

    def test_imports_follow_current_source_after_stale_export_fallback(self):
        current = "import Lean\n\ndef value : Nat := 2\n"
        files = export_files(current)
        files["A.leanquote"] = make_export(
            "def value : Nat := 1\n", source="import Init\n\ndef value : Nat := 1\n",
        )
        snippets, output = self.compile_tex(
            files, r"\leanquote[imports,file=A.lean,verify=true]{value}",
        )
        self.assertEqual(snippets, [current.strip()])
        self.assertIn("Reading A.lean directly", " ".join(output.split()))

    def test_line_boundaries_cannot_collide(self):
        old = 'def text : String := "a|\nb"\n'
        current = 'def text : String := "a\n|b"\n'
        files = export_files(current, name="text")
        files["A.leanquote"] = make_export(old, name="text")
        snippets, output = self.compile_tex(files, r"\leanquote[file=A.lean]{text}")
        self.assertEqual(snippets, [current.strip()])
        self.assertIn("Reading A.lean directly", " ".join(output.split()))

    def test_explicit_stale_export_is_marked(self):
        files = export_files()
        files["A.lean"] = "def value : Nat := 2\n"
        snippets, output = self.compile_tex(
            files, r"\leanquote[file=A.leanquote,verify=true]{value}",
        )
        self.assertEqual(snippets, ["def value : Nat := 1"])
        self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)

    def test_changed_build_fingerprint_invalidates_axioms(self):
        files = export_files()
        files["A.trace"] = '{"depHash": "rebuilt-with-sorry"}'
        _, output = self.compile_tex(files, r"\leanquote[file=A.lean,verify=true]{value}")
        self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)
        self.assertIn("build provenance", output)

    def test_matching_build_uses_axioms(self):
        files = export_files(axioms="sorryAx")
        _, output = self.compile_tex(files, r"\leanquote[file=A.lean,verify=true]{value}")
        self.assertIn("LEANQUOTE-BADGE:USES SORRY", output)
        self.assertNotIn("LEANQUOTE-BADGE:UNVERIFIED", output)

    def test_markers_inside_code_are_preserved(self):
        code = 'def text : String := "hello\n@@end\n@@doc literal\n@@src literal\nworld"\n'
        snippets, _ = self.compile_tex(
            export_files(code, name="text"), r"\leanquote[file=A.lean]{text}",
        )
        self.assertEqual(snippets, [code.strip()])

    def test_legacy_export_is_unverified_but_remains_readable(self):
        files = {"A.leanquote": (
            "@@leanquote-export 1\n@@begin value\n@@axioms\n"
            "def value : Nat := 1\n@@end\n"
        )}
        snippets, output = self.compile_tex(files, r"\leanquote[file=A.leanquote]{value}")
        self.assertEqual(snippets, ["def value : Nat := 1"])
        self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)

    def test_missing_axioms_are_not_treated_as_empty_axioms(self):
        files = export_files()
        files["A.leanquote"] = files["A.leanquote"].replace("@@axioms \n", "")
        _, output = self.compile_tex(files, r"\leanquote[file=A.leanquote]{value}")
        self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)
        self.assertIn("has no axiom information", " ".join(output.split()))

    def test_portable_snapshot_is_strictly_unverified_without_build(self):
        files = export_files()
        del files["A.olean"]
        del files["A.trace"]
        _, output = self.compile_tex(files, r"""
\leanquote[file=A.leanquote,verify=auto]{value}
\leanquote[file=A.leanquote,verify=true]{value}
""")
        self.assertEqual(output.count("LEANQUOTE-BADGE:UNVERIFIED"), 1)

    def test_actual_compiled_path_handles_custom_layout(self):
        code = "def value : Nat := 1\n"
        files = {
            "project/src/A.lean": code,
            "project/.lake/build/leanquote/src/A.leanquote": make_export(
                code, source_path="src/A.lean", olean="out/lib/A.olean",
            ),
            "project/out/lib/A.olean": "compiled",
            "project/out/lib/A.trace": '{"depHash": "build-a"}',
        }
        snippets, output = self.compile_tex(
            files, r"\leanquote[project=project/,file=src/A.lean,verify=true]{value}",
        )
        self.assertEqual(snippets, [code.strip()])
        self.assertNotIn("LEANQUOTE-BADGE:", output)

    def test_explicit_source_root(self):
        code = "def value : Nat := 1\n"
        files = {
            "project/A.lean": code,
            "A.leanquote": make_export(code),
            "project/A.olean": "compiled",
            "project/A.trace": '{"depHash": "build-a"}',
        }
        _, output = self.compile_tex(
            files, r"\leanquote[file=A.leanquote,root=project/,verify=true]{value}",
        )
        self.assertNotIn("LEANQUOTE-BADGE:", output)

    def test_unknown_export_version_is_rejected(self):
        files = {"A.leanquote": make_export("def value : Nat := 1\n").replace(
            "@@leanquote-export 2", "@@leanquote-export 99",
        )}
        self.compile_tex(files, r"\leanquote[file=A.leanquote]{value}", success=False)


if __name__ == "__main__":
    unittest.main()
