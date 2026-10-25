"""Source-parser integration tests; run with python3 tests/test_parsing.py.

Set LEANQUOTE_TEX_ENGINE to pdflatex, lualatex, or xelatex. If Lean is available,
the representative source fixtures are also checked by Lean itself.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ENGINE = os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")
PACKAGE = Path(__file__).resolve().parents[1] / "latex" / "leanquote.sty"


def source(text):
    return textwrap.dedent(text).strip() + "\n"


NAMESPACES = source("""
    namespace A
    def foo : Nat := 1
    public noncomputable section Inner
    namespace Nested.Deep
    def foo : Nat := 2
    end Nested.Deep
    end Inner
    mutual
      def helper : Nat := 0
    end
    def after : Nat := 3
    end A
    namespace B
    def foo : Nat := 4
    end B
    def Root.child : Nat := 5
    namespace Outer
    def _root_.globalValue : Nat := 6
    end Outer
""")

COMMENTS = source('''
    /- Ordinary comment.
    def phantom : Nat := 0
    /- nested comment -/
    def nestedGhost : Nat := 0
    namespace Wrong
    -/
    def text : String := "start
    def stringGhost : Nat := 0
    /-- fake documentation -/
    end"
    /-- Real documentation.
    /- Nested documentation comment. -/
    More documentation. -/
    @[simp]
    def phantom : Nat := 7
''')

METADATA = source("""
    /-- Unrelated documentation. -/
    @[simp] def previous : Nat := 1
    def wanted : Nat := 2
    /-- Kept documentation. -/
    @[simp]
    def kept : Nat := 3
""")

PROOFS = source(r'''
    module
    public theorem escaped (s : String := "a\" ] := ( /- --") : s = s := by
      rfl
    public theorem multiline
        (s : String := "first
    := ] -- /-
    last")
        /- outside comment with := ]
        /- nested -/ ) -/
        : s = s := by
      rfl
    theorem literal : "]:=" = "]:=" := by
      rfl
    public def body : String := "keep := [ /- --"
    public meta def helper : Nat := 8
    theorem character (c : Char := '"') : c = c := by
      rfl
    theorem raw (s : String := r##"quote " ] := /- --"##) : s = s := by
      rfl
    theorem unicode ⦃s : String⦄ : s = s := by
      rfl
''')

IMPORTS = source('''
    /- Copyright.
    /- Nested header. -/
    import Fake.Header
    -/
    module
    public import Init
    /- Between imports.
    /- nested -/
    import Fake.Middle
    -/
    meta import Lean
    -- import Fake.Line
    /- another comment -/
    import Init.Data.Nat.Basic -- retained trailing comment
    def text : String := "import Fake.String"
''')

INTERPOLATION = source(r'''
    def text : String := s!"{"first
    def phantom : Nat := 99
    last"}"
    def nested : String := s!"outer {s!"inner {r##"first
    def rawGhost : Nat := 99
    last"##}"} tail"
    def holes : String := s!"{ /- } " /- nested -/ -/
      ( { val := 1, isLt := by decide } : Fin 2).val
      -- } "
    } {'}'} {'"'} {'{'} {'\\'}"
    theorem interpolation : s!"{"first
    := ] -- /-
    last"}" = s!"{"first
    := ] -- /-
    last"}" := by
      rfl
    theorem nestedInterpolation : s!"{s!"{r#"a := ] } "#}"}" = "a := ] } " := by
      rfl
    def afterInterpolation : Nat := 7
''')

ESCAPED_NAMES = source('''
    namespace «A B»
    def foo : Nat := 1
    namespace «C D».Deep
    def «value with spaces» : Nat := 2
    def «dot.name».«leaf name» : Nat := 3
    def _root_.«global name» : Nat := 4
    end «C D».Deep
    def after : Nat := 5
    end «A B»
    namespace «A.B»
    def foo : Nat := 6
    end «A.B»
    namespace «comment/- and "quote»
    def «dash-- and /- comment» : Nat := 7
    end «comment/- and "quote»
    def «ordinary» : Nat := 8
''')

MULTILINE_IMPORTS = source('''
    /- header
    -/ import /- before module -/ Init /- first
    continued /- nested -/ -/ /- second -/ import Lean /- third
    -/ /- fourth -/
    import Init.«Data».Nat.Basic /- fifth -/ -- sixth
    def after : Nat := 1
''')


class ParsingTests(unittest.TestCase):
    def check_lean(self, work, filename, *, olean=False):
        command = ["lean"]
        if olean:
            command += ["-o", str(Path(filename).with_suffix(".olean"))]
        result = subprocess.run(
            command + [filename], cwd=work, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        if olean:
            self.assertTrue((work / Path(filename).with_suffix(".olean")).is_file())

    def compile(self, lean, body, *, success=True, export=None, olean=False):
        with tempfile.TemporaryDirectory(prefix="leanquote-parsing-") as directory:
            work = Path(directory)
            shutil.copyfile(PACKAGE, work / "leanquote.sty")
            (work / "Fixture.lean").write_text(lean, encoding="utf-8")
            if olean:
                self.check_lean(work, "Fixture.lean", olean=True)
            if export is not None:
                (work / "Saved.leanquote").write_text(export, encoding="utf-8")
            (work / "parsing.tex").write_text("\n".join([
                r"\documentclass{article}", r"\usepackage[T1]{fontenc}",
                r"\usepackage{leanquote}",
                r"\leanquotesetup{verify=false,box=false}",
                r"\leanquotesetup{file=Fixture.lean}",
                r"\begin{document}", body, r"\end{document}", "",
            ]), encoding="utf-8")
            result = subprocess.run(
                [ENGINE, "-halt-on-error", "-interaction=nonstopmode", "parsing.tex"],
                cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode == 0, success, result.stdout[-5000:])
            paths = sorted(work.glob("parsing-leanquote-*.lean"),
                           key=lambda path: int(path.stem.rsplit("-", 1)[1]))
            return [path.read_text(encoding="utf-8").strip() for path in paths], result.stdout

    def test_namespaces_sections_and_dotted_suffixes(self):
        snippets, output = self.compile(NAMESPACES, r'''
\leanquote{A.foo}
\leanquote{A.Nested.Deep.foo}
\leanquote{Deep.foo}
\leanquote{A.after}
\leanquote{B.foo}
\leanquote{Root.child}
\leanquote{globalValue}
''')
        self.assertEqual(snippets, [f"def {name} : Nat := {value}" for name, value in [
            ("foo", 1), ("foo", 2), ("foo", 2), ("after", 3), ("foo", 4),
            ("Root.child", 5), ("_root_.globalValue", 6),
        ]])
        self.assertNotIn("matches several declarations", output)
        snippets, output = self.compile(NAMESPACES, r"\leanquote{foo}")
        self.assertEqual(snippets, ["def foo : Nat := 1"])
        self.assertIn("matches several declarations", output)

    def test_unknown_qualified_names_error(self):
        for name in ["Missing.foo", "Missing.child", "A.Inner.after", "A.globalValue"]:
            with self.subTest(name=name):
                _, output = self.compile(NAMESPACES, r"\leanquote{" + name + "}", success=False)
                self.assertIn("not found", output)

    def test_escaped_namespace_and_declaration_components(self):
        snippets, _ = self.compile(ESCAPED_NAMES, r'''
\leanquote{«A B».foo}
\leanquote{«A B».«C D».Deep.«value with spaces»}
\leanquote{Deep.«dot.name».«leaf name»}
\leanquote{«global name»}
\leanquote{_root_.«global name»}
\leanquote{_root_.«A B».foo}
\leanquote{«A B».after}
\leanquote{«A.B».foo}
\leanquote{«comment/- and "quote».«dash-- and /- comment»}
\leanquote{ordinary}
''')
        self.assertEqual(snippets, [
            "def foo : Nat := 1", "def «value with spaces» : Nat := 2",
            "def «dot.name».«leaf name» : Nat := 3",
            "def _root_.«global name» : Nat := 4",
            "def _root_.«global name» : Nat := 4", "def foo : Nat := 1", "def after : Nat := 5",
            "def foo : Nat := 6", 'def «dash-- and /- comment» : Nat := 7',
            "def «ordinary» : Nat := 8",
        ])
        for name in ["A.B.foo", "B».foo", "«A B».«global name»", "name».«leaf name»", "_root_.foo"]:
            with self.subTest(name=name):
                _, output = self.compile(ESCAPED_NAMES, r"\leanquote{" + name + "}", success=False)
                self.assertRegex(output, r"not\s+(?:\(leanquote\)\s*)?found")

    def test_nested_comments_strings_and_documentation(self):
        snippets, output = self.compile(COMMENTS, r"\leanquote[doc]{phantom}\leanquote{text}")
        self.assertEqual(snippets, [
            "/-- Real documentation.\n/- Nested documentation comment. -/\n"
            "More documentation. -/\n@[simp]\ndef phantom : Nat := 7",
            'def text : String := "start\ndef stringGhost : Nat := 0\n'
            '/-- fake documentation -/\nend"',
        ])
        self.assertNotIn("matches several declarations", output)
        for name in ["nestedGhost", "stringGhost"]:
            with self.subTest(name=name):
                _, output = self.compile(COMMENTS, r"\leanquote{" + name + "}", success=False)
                self.assertIn("not found", output)

    def test_inline_attributes_do_not_leak_metadata(self):
        snippets, _ = self.compile(METADATA, r"\leanquote[doc]{wanted}\leanquote[doc]{kept}")
        self.assertEqual(snippets, [
            "def wanted : Nat := 2",
            "/-- Kept documentation. -/\n@[simp]\ndef kept : Nat := 3",
        ])

    def test_proof_hiding_uses_lexical_state_and_modifiers(self):
        snippets, _ = self.compile(PROOFS, r'''
\leanquote[proof=false]{escaped}
\leanquote[proof=false]{multiline}
\leanquote[proof=false]{literal}
\leanquote[proof=false]{body}
\leanquote[proof=false]{helper}
\leanquote[proof=false]{character}
\leanquote[proof=false]{raw}
\leanquote[proof=false]{unicode}
''')
        escaped = PROOFS.splitlines()[1].split(" := by")[0] + " := ..."
        multiline = PROOFS.split("public theorem multiline\n", 1)[1].split(" := by", 1)[0]
        self.assertEqual(snippets, [
            escaped, "public theorem multiline\n" + multiline + " := ...",
            'theorem literal : "]:=" = "]:=" := ...',
            'public def body : String := "keep := [ /- --"',
            "public meta def helper : Nat := 8",
            "theorem character (c : Char := '\"') : c = c := ...",
            'theorem raw (s : String := r##"quote " ] := /- --"##) : s = s := ...',
            'theorem unicode ⦃s : String⦄ : s = s := ...',
        ])

    def test_export_proof_hiding_uses_same_scanner(self):
        declaration = PROOFS.split("public theorem escaped", 1)[1].split("public theorem multiline", 1)[0].strip()
        declaration = "public theorem escaped" + declaration
        exported = "@@leanquote-export 1\n@@begin escaped\n@@axioms\n" + declaration + "\n@@end\n"
        snippets, _ = self.compile("", r"\leanquote[file=Saved.leanquote,proof=false]{escaped}", export=exported)
        self.assertEqual(snippets, [declaration.split(" := by")[0] + " := ..."])

    def test_export_inline_doc_theorem_keeps_leading_space(self):
        exported = ("@@leanquote-export 2\n@@begin inline\n@@axioms\n"
                    "@@doc /-- Inline documentation. -/\n"
                    "@@code  theorem inline : True := by\n@@code   trivial\n@@end\n")
        snippets, _ = self.compile("", r"\leanquote[file=Saved.leanquote,doc,proof=false]{inline}", export=exported)
        self.assertEqual(snippets, ["/-- Inline documentation. -/\n theorem inline : True := ..."])

    @unittest.skipUnless(shutil.which("lean"), "Lean is not installed")
    def test_compiled_interpolated_strings_do_not_declare_phantoms(self):
        for name in ["phantom", "rawGhost"]:
            with self.subTest(name=name):
                _, output = self.compile(
                    INTERPOLATION,
                    r"\leanquote[file=Fixture.lean,olean=Fixture.olean,verify=true]{" + name + "}",
                    success=False, olean=True,
                )
                self.assertIn("not found", output)
                self.assertNotIn("UNVERIFIED", output)

    def test_interpolation_proof_cuts_preserve_source_offsets(self):
        snippets, _ = self.compile(INTERPOLATION, r'''
\leanquote{text}
\leanquote{nested}
\leanquote{holes}
\leanquote[proof=false]{interpolation}
\leanquote[proof=false]{nestedInterpolation}
\leanquote{afterInterpolation}
''')
        declarations = ["def text", "def nested", "def holes", "theorem interpolation",
                        "theorem nestedInterpolation", "def afterInterpolation"]
        expected = []
        for index, header in enumerate(declarations):
            declaration = header + INTERPOLATION.split(header, 1)[1]
            if index + 1 < len(declarations):
                declaration = declaration.split(declarations[index + 1], 1)[0]
            if header.startswith("theorem"):
                declaration = declaration.split(" := by", 1)[0] + " := ..."
            expected.append(declaration.strip())
        self.assertEqual(snippets, expected)
        exported = ("@@leanquote-export 1\n@@begin interpolation\n@@axioms\n" +
                    expected[3].removesuffix(" := ...") + " := by\n  rfl\n@@end\n")
        saved, _ = self.compile("", r"\leanquote[file=Saved.leanquote,proof=false]{interpolation}", export=exported)
        self.assertEqual(saved, [expected[3]])

    def test_imports_skip_nested_comments_between_commands(self):
        snippets, _ = self.compile(IMPORTS, r"\leanquote[imports]{}")
        self.assertEqual(snippets, [
            "module\npublic import Init\nmeta import Lean\n"
            "import Init.Data.Nat.Basic",
        ])
        exported = "@@leanquote-export 1\n" + "".join("@@src " + line + "\n" for line in IMPORTS.splitlines())
        saved, _ = self.compile("", r"\leanquote[imports,file=Saved.leanquote]{}", export=exported)
        self.assertEqual(saved, snippets)

    def test_import_comments_spanning_command_lines(self):
        for lean in [MULTILINE_IMPORTS, source('''
            import Init /- comment
            continued -/
            import Lean
        '''), source('''
            /- header
            -/ import Init
            import Lean
        ''')]:
            with self.subTest(lean=lean):
                snippets, _ = self.compile(lean, r"\leanquote[imports]{}")
                exported = "@@leanquote-export 1\n" + "".join(
                    "@@src " + line + "\n" for line in lean.splitlines())
                saved, _ = self.compile("", r"\leanquote[imports,file=Saved.leanquote]{}", export=exported)
                self.assertEqual(saved, snippets)
                self.assertNotIn("/-", snippets[0])
                self.assertNotIn("-/", snippets[0])
                self.assertEqual(snippets[0].split(), [
                    "import", "Init", "import", "Lean", "import", "Init.«Data».Nat.Basic",
                ] if lean == MULTILINE_IMPORTS else ["import", "Init", "import", "Lean"])

    def test_fake_imports_do_not_start_a_header(self):
        snippets, output = self.compile(source('''
            /- /- nested -/
            import Fake.Comment
            -/
            def text : String := "import Fake.String"
        '''), r"\leanquote[imports]{}", success=False)
        self.assertEqual(snippets, [""])
        self.assertIn("No import lines found", output)

    @unittest.skipUnless(shutil.which("lean"), "Lean is not installed")
    def test_representative_fixtures_are_valid_lean(self):
        with tempfile.TemporaryDirectory(prefix="leanquote-valid-fixtures-") as directory:
            work = Path(directory)
            for name, content in [
                ("Namespaces", NAMESPACES), ("Comments", COMMENTS),
                ("Metadata", METADATA), ("Proofs", PROOFS), ("Imports", IMPORTS),
                ("Interpolation", INTERPOLATION), ("EscapedNames", ESCAPED_NAMES),
                ("MultilineImports", MULTILINE_IMPORTS),
            ]:
                with self.subTest(fixture=name):
                    filename = name + ".lean"
                    (work / filename).write_text(content, encoding="utf-8")
                    self.check_lean(work, filename, olean=True)


if __name__ == "__main__":
    unittest.main()
