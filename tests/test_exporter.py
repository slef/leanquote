"""Exporter regressions: python3 tests/test_exporter.py (stdlib + Lean/Lake + sh).

Set LEANQUOTE_LEAN_TOOLCHAIN to select an installed Elan toolchain, e.g.
leanprover/lean4:v4.35.0. TeX is optional for the writer/reader integration test;
the remaining exporter tests need no TeX installation or network access.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "lean" / "LeanQuoteExport.lean"
WRAPPER = ROOT / "leanquote-export"
CONFIG = '''name = "exporter_fixture"
version = "0.1.0"
srcDir = "package-src"
buildDir = "artifacts"
leanLibDir = "objects"

[[lean_lib]]
name = "Demo"
srcDir = "lib-src"

[[lean_lib]]
name = "Dependency"
srcDir = "lib-src"
'''
SOURCE = '''import Dependency
namespace Example
/-- Structure docs. -/
structure Data where
  /-- A field /- with nesting -/. -/
  value : Nat
  other : Nat
structure Named where
  make ::
  count : Nat
/-- Choice docs. -/
inductive Choice where | one | two
inductive Elim where | elim
/-- Blue docs. -/
inductive Color where
  /-- A constructor /- nested -/. -/ | blue
/-- Inline /- nested -/ docs. -/ def inlineDoc : Nat := 1
/-- Multi-line /- nested
comment -/ docs
end here -/ def multiDoc : Nat := 2
private def secret : Nat := 2
private theorem hidden : False := by sorry
def sameA : Nat := 3 def sameB : Nat := 4
def café : Nat := 5 def «odd name» : Nat := 6
axiom assumed : True
theorem usesAssumed : True := assumed
theorem usesDependency : True := dependency
theorem unfinished : False := by sorry
def marker : String := "header

@@end
@@begin forged
@@axioms sorryAx
@@code forged
@@doc forged
@@src forged
footer"
end Example
'''


def native_path(path):
    """Cygwin Python must pass native paths to native Lean; Linux needs no conversion."""
    path = str(path)
    if os.name != "nt" and shutil.which("cygpath"):
        return subprocess.check_output(["cygpath", "-m", path], text=True).strip()
    return path


def run(work, *args, success=True):
    result = subprocess.run(
        list(args), cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=240,
    )
    if (result.returncode == 0) != success:
        raise AssertionError(f"{args!r}: exit {result.returncode}\n{result.stdout}")
    return result.stdout


def parse_export(text):
    """Strict decoder: any unprefixed record payload is a protocol error."""
    headers, entries, snapshot = {}, {}, []
    current = None
    for line in text.splitlines():
        if line.startswith("@@begin "):
            assert current is None, line
            name = line.removeprefix("@@begin ")
            assert name not in entries, name
            current = {"doc": [], "code": []}
            entries[name] = current
        elif line == "@@end":
            assert current is not None
            assert "axioms" in current
            current = None
        elif current is not None:
            tag, _, value = line.partition(" ")
            if tag == "@@axioms":
                assert "axioms" not in current
                current["axioms"] = value.split()
            elif tag in ("@@doc", "@@code"):
                current[tag[2:]].append(value)
            else:
                raise AssertionError(f"unframed declaration line: {line!r}")
        elif line.startswith("@@src ") or line == "@@src":
            snapshot.append(line[6:] if line.startswith("@@src ") else "")
        else:
            tag, _, value = line.partition(" ")
            assert tag not in headers, tag
            headers[tag] = value
    assert current is None
    return headers, entries, snapshot


class ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="leanquote-exporter-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        if toolchain := os.environ.get("LEANQUOTE_LEAN_TOOLCHAIN"):
            (cls.work / "lean-toolchain").write_text(toolchain + "\n", encoding="utf-8")
        (cls.work / "lakefile.toml").write_text(CONFIG, encoding="utf-8")
        cls.src = cls.work / "package-src" / "lib-src" / "Demo.lean"
        cls.src.parent.mkdir(parents=True)
        cls.src.write_text(SOURCE, encoding="utf-8")
        cls.dep = cls.src.with_name("Dependency.lean")
        cls.dep.write_text("theorem dependency : True := by trivial\n", encoding="utf-8")
        # A malicious-looking root shadow must never supply text for the real build.
        (cls.work / "Demo.lean").write_text(
            "namespace Example\ntheorem usesDependency : False := by sorry\nend Example\n",
            encoding="utf-8",
        )
        cls.shell = shutil.which("sh")
        if not cls.shell:
            raise RuntimeError("test_exporter.py requires a POSIX sh")
        run(cls.work, cls.shell, native_path(WRAPPER), "Demo")
        cls.out = cls.work / ".lake/build/leanquote/package-src/lib-src/Demo.leanquote"
        cls.text = cls.out.read_text(encoding="utf-8")
        cls.headers, cls.entries, cls.snapshot = parse_export(cls.text)

    def code(self, name):
        return "\n".join(self.entries["Example." + name]["code"])

    def doc(self, name):
        return "\n".join(self.entries["Example." + name]["doc"])

    def direct(self, source, output="direct.leanquote", *, success=True):
        return run(self.work, "lake", "env", "lean", "--run", native_path(CLI),
                   "Demo", source, output, success=success)

    def test_lake_source_and_artifact_provenance(self):
        self.assertEqual(self.headers["@@leanquote-export"], "2")
        self.assertEqual(self.headers["@@module"], "Demo")
        self.assertEqual(self.headers["@@source"], "package-src/lib-src/Demo.lean")
        self.assertEqual(self.headers["@@olean"], "artifacts/objects/Demo.olean")
        artifact = self.work / self.headers["@@olean"]
        self.assertTrue(artifact.is_file())
        trace = json.loads(artifact.with_suffix(".trace").read_text(encoding="utf-8"))
        self.assertEqual(self.headers["@@trace"], trace["depHash"])
        self.assertFalse(self.headers["@@trace"].startswith('"'))
        self.assertEqual(self.snapshot, [line.rstrip() for line in SOURCE.splitlines()])
        self.assertEqual(self.entries["Example.usesDependency"]["axioms"], [])

    def test_structure_and_constructor_names(self):
        self.assertEqual(self.doc("Data"), "/-- Structure docs. -/")
        self.assertTrue(self.code("Data").startswith("structure Data where\n"))
        self.assertEqual(self.code("Named.make"), "make ::")
        self.assertEqual(self.code("Choice.one"), "| one")
        self.assertEqual(self.code("Choice.two"), "| two")
        self.assertNotIn("Example.Data.rec", self.entries)
        self.assertNotIn("Example.Color.blue.elim", self.entries)
        self.assertEqual(self.code("Elim.elim"), "| elim")
        self.assertNotIn("Example.Elim.elim.elim", self.entries)
        self.assertNotIn("Example.Data.mk", self.entries)  # implicit, no source name

    def test_field_docs_and_full_field_slices(self):
        self.assertEqual(self.doc("Data.value"), "/-- A field /- with nesting -/. -/")
        self.assertEqual(self.code("Data.value"), "  value : Nat")
        self.assertEqual(self.doc("Data.other"), "")
        self.assertEqual(self.code("Data.other"), "other : Nat")
        self.assertEqual(self.doc("Color.blue"), "/-- A constructor /- nested -/. -/")
        self.assertEqual(self.code("Color.blue"), " | blue")

    def test_inline_and_nested_doc_boundaries(self):
        self.assertEqual(self.doc("inlineDoc"), "/-- Inline /- nested -/ docs. -/")
        self.assertEqual(self.code("inlineDoc"), " def inlineDoc : Nat := 1")
        self.assertEqual(self.doc("multiDoc"),
                         "/-- Multi-line /- nested\ncomment -/ docs\nend here -/")
        self.assertEqual(self.code("multiDoc"), " def multiDoc : Nat := 2")

    def test_private_names_and_axioms(self):
        self.assertIn("\n@@axioms\n", self.text)  # explicit empty dependency list
        self.assertNotIn("\n@@axioms \n", self.text)
        self.assertEqual(self.code("secret"), "private def secret : Nat := 2")
        self.assertIn("sorryAx", self.entries["Example.hidden"]["axioms"])
        self.assertFalse(any(name.startswith("_private.") for name in self.entries))
        self.assertIn("Example.assumed", self.entries["Example.usesAssumed"]["axioms"])
        self.assertIn("sorryAx", self.entries["Example.unfinished"]["axioms"])

    def test_modern_module_private_declarations(self):
        config = self.work / "lakefile.toml"
        old = config.read_text(encoding="utf-8")
        modern = self.src.with_name("Modern.lean")
        modern.write_text(
            "module\npublic import Init\nnamespace Example\n"
            "private def hiddenValue : Nat := 1\n"
            "private theorem hiddenTruth : True := by trivial\n"
            "public theorem usesHidden : True := hiddenTruth\nend Example\n",
            encoding="utf-8",
        )
        try:
            config.write_text(old + '''
[[lean_lib]]
name = "Modern"
srcDir = "lib-src"
''', encoding="utf-8")
            run(self.work, self.shell, native_path(WRAPPER), "Modern")
            path = self.out.with_name("Modern.leanquote")
            _, entries, _ = parse_export(path.read_text(encoding="utf-8"))
            self.assertEqual(entries["Example.hiddenValue"]["code"],
                             ["private def hiddenValue : Nat := 1"])
            self.assertEqual(entries["Example.hiddenTruth"]["axioms"], [])
            self.assertEqual(entries["Example.usesHidden"]["axioms"], [])
        finally:
            config.write_text(old, encoding="utf-8")
            modern.unlink()

    @unittest.skipUnless(shutil.which(os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")),
                         "TeX is not installed")
    def test_latex_rejects_old_export_after_dependency_rebuild(self):
        engine = os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")
        old = self.dep.read_text(encoding="utf-8")
        shutil.copyfile(ROOT / "latex/leanquote.sty", self.work / "leanquote.sty")
        (self.work / "provenance.tex").write_text(r"""
\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage{leanquote}
\leanquotesetup{box=false,verify=true}
\renewcommand{\leanquotebadgetext}[1]{\typeout{LEANQUOTE-BADGE:#1}}
\begin{document}
\leanquote[file=package-src/lib-src/Demo.lean]{Example.usesDependency}
\end{document}
""", encoding="utf-8")
        try:
            run(self.work, self.shell, native_path(WRAPPER), "Demo")
            original = self.out.read_text(encoding="utf-8")
            self.dep.write_text("theorem dependency : True := by sorry\n", encoding="utf-8")
            run(self.work, "lake", "-H", "build", "Demo")
            self.assertEqual(self.out.read_text(encoding="utf-8"), original)
            output = run(self.work, engine, "-halt-on-error", "-interaction=nonstopmode",
                         "provenance.tex")
            self.assertIn("LEANQUOTE-BADGE:UNVERIFIED", output)
            run(self.work, self.shell, native_path(WRAPPER), "Demo")
            output = run(self.work, engine, "-halt-on-error", "-interaction=nonstopmode",
                         "provenance.tex")
            self.assertIn("LEANQUOTE-BADGE:USES SORRY", output)
            self.assertNotIn("LEANQUOTE-BADGE:UNVERIFIED", output)
        finally:
            self.dep.write_text(old, encoding="utf-8")
            run(self.work, self.shell, native_path(WRAPPER), "Demo")

    def test_same_line_and_unicode_positions(self):
        self.assertEqual(self.code("sameA"), "def sameA : Nat := 3")
        self.assertEqual(self.code("sameB"), "def sameB : Nat := 4")
        self.assertEqual(self.code("café"), "def café : Nat := 5")
        self.assertEqual(self.code("«odd name»"), "def «odd name» : Nat := 6")

    def test_marker_and_empty_payload_lines(self):
        expected = "def marker" + SOURCE.split("def marker", 1)[1].split("\nend Example", 1)[0]
        self.assertEqual(self.code("marker"), expected)
        self.assertIn("@@code \n@@code @@end\n", self.text)
        self.assertNotIn("forged", self.entries)

    def test_direct_cli_rejects_shadow_source(self):
        output = self.direct("Demo.lean", "rejected.leanquote", success=False)
        self.assertIn("source mismatch", output)
        self.assertFalse((self.work / "rejected.leanquote").exists())

    def test_direct_cli_checks_source_and_builds(self):
        self.direct("package-src/lib-src/Demo.lean")
        direct = (self.work / "direct.leanquote").read_text(encoding="utf-8")
        self.assertEqual(direct, self.text)

    def test_cached_lean_lakefile_loads_native_support(self):
        # Unlike the TOML fixtures, cached Lean configurations exercise Lake's
        # native configuration loader. The unbootstrapped --run exporter aborts
        # in the IR interpreter here, without needing Mathlib or any downloads.
        with tempfile.TemporaryDirectory(prefix="leanquote-lean-config-") as directory:
            work = Path(directory)
            if (self.work / "lean-toolchain").exists():
                shutil.copyfile(self.work / "lean-toolchain", work / "lean-toolchain")
            (work / "lakefile.lean").write_text('''import Lake
open Lake DSL
package exporter_lean_fixture where
  srcDir := "src"
  buildDir := "artifacts"
  leanLibDir := "objects"
lean_lib Demo
''', encoding="utf-8")
            (work / "src").mkdir()
            source = "/-- A theorem from a Lean-configured project. -/\n" \
                     "theorem value : True := by sorry\n"
            (work / "src/Demo.lean").write_text(source, encoding="utf-8")
            run(work, "lake", "build", "Demo")  # populate the configuration cache
            run(work, self.shell, native_path(WRAPPER), "Demo")
            exported = work / ".lake/build/leanquote/src/Demo.leanquote"
            text = exported.read_text(encoding="utf-8")
            headers, entries, snapshot = parse_export(text)
            self.assertEqual(headers["@@source"], "src/Demo.lean")
            self.assertEqual(headers["@@olean"], "artifacts/objects/Demo.olean")
            trace = json.loads((work / "artifacts/objects/Demo.trace")
                               .read_text(encoding="utf-8"))
            self.assertEqual(headers["@@trace"], trace["depHash"])
            self.assertIn("sorryAx", entries["value"]["axioms"])
            self.assertEqual(snapshot, source.splitlines())
            # The documented direct CLI must bootstrap too, with no extra flags.
            run(work, "lake", "env", "lean", "--run", native_path(CLI),
                "Demo", "src/Demo.lean", "direct.leanquote")
            self.assertEqual((work / "direct.leanquote").read_text(encoding="utf-8"), text)

    def test_crlf_source_positions_and_doc_split(self):
        old = self.src.read_bytes()
        try:
            self.src.write_bytes(SOURCE.replace("\n", "\r\n").encode("utf-8"))
            self.direct("package-src/lib-src/Demo.lean", "crlf.leanquote")
            _, entries, snapshot = parse_export(
                (self.work / "crlf.leanquote").read_text(encoding="utf-8"))
            self.assertEqual(entries, self.entries)
            self.assertEqual(snapshot, self.snapshot)
        finally:
            self.src.write_bytes(old)

    def test_rebuild_tracks_dependency_axioms_with_unchanged_source(self):
        old = self.dep.read_text(encoding="utf-8")
        try:
            self.dep.write_text("theorem dependency : True := by sorry\n", encoding="utf-8")
            self.direct("package-src/lib-src/Demo.lean", "updated.leanquote")
            headers, entries, snapshot = parse_export(
                (self.work / "updated.leanquote").read_text(encoding="utf-8"))
            self.assertNotEqual(headers["@@trace"], self.headers["@@trace"])
            self.assertEqual(snapshot, self.snapshot)
            self.assertIn("sorryAx", entries["Example.usesDependency"]["axioms"])
            trace = json.loads((self.work / headers["@@olean"]).with_suffix(".trace")
                               .read_text(encoding="utf-8"))
            self.assertEqual(headers["@@trace"], trace["depHash"])
        finally:
            self.dep.write_text(old, encoding="utf-8")

    def test_source_edit_is_rebuilt_before_export(self):
        old = self.src.read_bytes()
        changed = SOURCE.replace("theorem usesAssumed : True := assumed",
                                 "theorem usesAssumed : True := by trivial")
        try:
            self.src.write_text(changed, encoding="utf-8")
            self.direct("package-src/lib-src/Demo.lean", "source-edited.leanquote")
            headers, entries, snapshot = parse_export(
                (self.work / "source-edited.leanquote").read_text(encoding="utf-8"))
            self.assertNotEqual(headers["@@trace"], self.headers["@@trace"])
            self.assertEqual(entries["Example.usesAssumed"]["axioms"], [])
            self.assertEqual(entries["Example.usesAssumed"]["code"],
                             ["theorem usesAssumed : True := by trivial"])
            self.assertEqual(snapshot, changed.splitlines())
        finally:
            self.src.write_bytes(old)

    def test_uncompilable_source_is_not_exported(self):
        old = self.src.read_bytes()
        try:
            self.src.write_text(SOURCE + "def broken : Nat :=\n", encoding="utf-8")
            output = self.direct("package-src/lib-src/Demo.lean", "broken.leanquote",
                                 success=False)
            self.assertIn("lake build Demo failed", output)
            self.assertFalse((self.work / "broken.leanquote").exists())
        finally:
            self.src.write_bytes(old)

    def test_ambiguous_lake_sources_are_rejected(self):
        config = self.work / "lakefile.toml"
        old = config.read_text(encoding="utf-8")
        other = self.work / "package-src" / "other"
        other.mkdir()
        (other / "Demo.lean").write_text("def shadow : Nat := 0\n", encoding="utf-8")
        try:
            config.write_text(old + '''
[[lean_lib]]
name = "Other"
roots = ["Demo"]
srcDir = "other"
''', encoding="utf-8")
            output = self.direct("package-src/lib-src/Demo.lean", success=False)
            self.assertIn("ambiguous Lake module Demo", output)
        finally:
            config.write_text(old, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
