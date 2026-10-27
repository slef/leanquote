"""Run with python3 tests/test_api.py; select TeX via LEANQUOTE_TEX_ENGINE."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from export_support import make_export

ENGINE = os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")
PACKAGE = Path(__file__).resolve().parents[1] / "latex" / "leanquote.sty"
VALUE = "def value : Nat := {}"
PROOF = "theorem truth : True := by\n  trivial"
HIDDEN_PROOF = "theorem truth : True := ..."
IMPORT_NAMES = 'def «import» : Nat := 3\n\ndef imports : Nat := 4'


class FileSelectionTests(unittest.TestCase):
    def compile(self, body, preamble="", *, before_package="", success=True):
        with tempfile.TemporaryDirectory(prefix="leanquote-api-") as directory:
            work = Path(directory)
            shutil.copyfile(PACKAGE, work / "leanquote.sty")
            project = work / "project"
            project.mkdir()
            for filename, module, value in [("A.lean", "Init", 1), ("B.lean", "Lean", 2)]:
                (project / filename).write_text(
                    f"import {module}\n\n/-- A value. -/\n{VALUE.format(value)}\n\n"
                    f"/-- A proof. -/\n{PROOF}\n",
                    encoding="utf-8",
                )
            (project / "Names.lean").write_text(
                "import Init\n\n" + IMPORT_NAMES + "\n", encoding="utf-8",
            )
            (project / "NoImports.lean").write_text(VALUE.format(9) + "\n", encoding="utf-8")
            saved = make_export(
                VALUE.format(7), source="import Init\n\n/-- A value. -/\n" + VALUE.format(7),
            ).replace("@@code def value", "@@doc /-- A value. -/\n@@code def value")
            (work / "Saved.leanquote").write_text(saved, encoding="utf-8")
            names = make_export('def «import» : Nat := 3', name="import",
                                source="import Init\n\n" + IMPORT_NAMES)
            names = names.replace("@@end\n", "@@end\n@@begin imports\n@@axioms\n"
                                  "@@code def imports : Nat := 4\n@@end\n", 1)
            (work / "Names.leanquote").write_text(names, encoding="utf-8")
            (work / "api.tex").write_text(
                "\n".join([
                    r"\documentclass{article}", r"\usepackage[T1]{fontenc}",
                    before_package, r"\usepackage{leanquote}",
                    r"\leanquotesetup{project=project/,verify=false,box=false}",
                    preamble, r"\begin{document}", body, r"\end{document}", "",
                ]),
                encoding="utf-8",
            )
            result = subprocess.run(
                [ENGINE, "-halt-on-error", "-interaction=nonstopmode", "api.tex"],
                cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(result.returncode == 0, success, result.stdout[-5000:])
            paths = sorted(
                work.glob("api-leanquote-*.lean"),
                key=lambda path: int(path.stem.rsplit("-", 1)[1]),
            )
            return [path.read_text(encoding="utf-8").strip() for path in paths], result.stdout

    def test_explicit_files_without_default(self):
        snippets, _ = self.compile(r"""
\leanquote[file=A.lean]{value}
\leanquote[imports,file=B.lean]{}
\leanquote[imports,file=B.lean]{value}
\leanquote[file=Saved.leanquote]{value}
\leanquote[file=B.lean,doc,proof=false,numbers=left]{truth}
""")
        self.assertEqual(snippets, [
            VALUE.format(1), "import Lean", "import Lean\n\n" + VALUE.format(2),
            VALUE.format(7), "/-- A proof. -/\n" + HIDDEN_PROOF,
        ])

    def test_default_options_overrides_and_grouping(self):
        snippets, _ = self.compile(r"""
\leanquote{value}
\leanquote[file=B.lean,doc=false,proof=true,numbers=none]{truth}
\leanquote{truth}
\leanquote[imports]{}
\leanquote[imports,file=B.lean]{}
\leanquote[imports]{}
{\leanquotesetup{file=B.lean,doc=false}\leanquote{value}}
\leanquote{value}
""", r"\leanquotesetup{file=A.lean,doc,proof=false,numbers=left}")
        documented_value = "/-- A value. -/\n" + VALUE.format(1)
        self.assertEqual(snippets, [
            documented_value, PROOF, "/-- A proof. -/\n" + HIDDEN_PROOF,
            "import Init", "import Lean", "import Init", VALUE.format(2), documented_value,
        ])

    def test_filename_macros_expand_at_quote_time(self):
        snippets, _ = self.compile(r"""
\leanquote{value}
\def\SelectedModule{B}
\leanquote[imports]{value}
\leanquote[file=\SavedExport]{value}
\leanquote{value}
""", r"""
\leanquotesetup{file=\SelectedFile}
\def\SelectedFile{\SelectedModule.lean}
\def\SelectedModule{A}
\def\SavedExport{Saved.leanquote}
""")
        self.assertEqual(snippets, [VALUE.format(1), "import Lean\n\n" + VALUE.format(2),
                                    VALUE.format(7), VALUE.format(2)])

    def test_setup_file_and_scoped_overrides(self):
        snippets, _ = self.compile(r"""
\leanquote{value}
\leanquote[file=B.lean]{value}
\leanquote{value}
{\leanquotesetup{file=B.lean}\leanquote{value}}
\leanquote{value}
""", r"\leanquotesetup{file=A.lean}")
        self.assertEqual(snippets, [VALUE.format(n) for n in [1, 2, 1, 2, 1]])

    def test_explicit_override_does_not_establish_default(self):
        for command in [r"\leanquote[file=A.lean]{value}", r"\leanquote[imports,file=A.lean]{}"]:
            with self.subTest(command=command):
                snippets, output = self.compile(command + r"\leanquote{value}", success=False)
                self.assertEqual(len(snippets), 1)
                self.assertIn("No Lean file specified", output)

    def test_missing_file_errors(self):
        for command in [r"\leanquote{value}", r"\leanquote[imports]{}"]:
            with self.subTest(command=command):
                _, output = self.compile(command, success=False)
                self.assertIn("No Lean file specified", output)
                self.assertIn("file=...", output)
        _, output = self.compile(r"\leanquote[file=Missing.lean]{value}", success=False)
        self.assertIn("not found", output)
        _, output = self.compile(
            r"\leanquote[file={}]{value}", r"\leanquotesetup{file=A.lean}", success=False,
        )
        self.assertIn("No Lean file specified", output)

    def test_imports_are_prepended_once_and_do_not_persist(self):
        snippets, _ = self.compile(r"""
\leanquote[imports]{value,truth}
\leanquote{value}
\leanquote[imports=true]{}
\leanquote[imports=false]{value}
""", r"\leanquotesetup{file=A.lean}")
        self.assertEqual(snippets, [
            "import Init\n\n" + VALUE.format(1) + "\n\n" + PROOF,
            VALUE.format(1), "import Init", VALUE.format(1),
        ])

    def test_imports_setup_overrides_and_grouping(self):
        snippets, _ = self.compile(r"""
\leanquote{value}
\leanquote[imports=false,file=B.lean]{value}
\leanquote{}
{\leanquotesetup{imports=false,file=B.lean}\leanquote{value}}
\leanquote{value}
""", r"\leanquotesetup{file=A.lean,imports}")
        self.assertEqual(snippets, [
            "import Init\n\n" + VALUE.format(1), VALUE.format(2), "import Init",
            VALUE.format(2), "import Init\n\n" + VALUE.format(1),
        ])

    def test_imports_with_docs_proof_hiding_and_export_input(self):
        snippets, _ = self.compile(r"""
\leanquote[imports,doc,proof=false,file=A.lean]{truth,value}
\leanquote[imports,doc,file=Saved.leanquote]{value}
\leanquote[imports,file=Saved.leanquote]{ }
""")
        self.assertEqual(snippets, [
            "import Init\n\n/-- A proof. -/\n" + HIDDEN_PROOF
            + "\n\n/-- A value. -/\n" + VALUE.format(1),
            "import Init\n\n/-- A value. -/\n" + VALUE.format(7), "import Init",
        ])

    def test_import_names_are_declarations_in_source_and_exports(self):
        snippets, _ = self.compile(r"""
\leanquote[file=Names.lean]{import,imports}
\leanquote[imports,file=Names.lean]{imports,import}
\leanquote[file=Names.leanquote]{import,imports}
\leanquote[imports,file=Names.leanquote]{imports,import}
""")
        self.assertEqual(snippets, [IMPORT_NAMES,
            'import Init\n\ndef imports : Nat := 4\n\ndef «import» : Nat := 3',
            IMPORT_NAMES,
            'import Init\n\ndef imports : Nat := 4\n\ndef «import» : Nat := 3',
        ])

    def test_missing_imports_and_removed_selector_errors(self):
        _, output = self.compile(r"\leanquote[imports,file=NoImports.lean]{}", success=False)
        self.assertIn("No import lines found", output)
        _, output = self.compile(r"\leanquote[file=A.lean]{:imports}", success=False)
        self.assertIn("not found", output)

    def test_imports_inside_figures_macros_and_footnotes(self):
        snippets, _ = self.compile(r"""
\begin{figure}
  \leanquote[imports,box=true]{value}
  \caption{Imports and a declaration.}
\end{figure}
\newcommand{\wrapper}[1]{#1}
\wrapper{\leanquote[imports]{value}}
Text\footnote{\leanquote[imports,box=true]{value}}.
""", r"\leanquotesetup{file=A.lean}")
        self.assertEqual(snippets, ["import Init\n\n" + VALUE.format(1)] * 3)

    def test_removed_command_names_are_free(self):
        self.compile(r"""
\ifdefined\leanfile\errmessage{leanfile is still defined}\fi
\ifdefined\leanfilequote\errmessage{leanfilequote is still defined}\fi
\ifdefined\leanquotefrom\errmessage{leanquotefrom should not be defined}\fi
\ifdefined\leanquotefile\errmessage{leanquotefile is still defined}\fi
\ifdefined\leanquoteimports\errmessage{leanquoteimports is still defined}\fi
\ifdefined\imports\errmessage{imports marker should not be defined}\fi
\newcommand{\leanfile}{Other package's command}
\newcommand{\leanfilequote}{Other package's command}
\newcommand{\leanquotefile}{Other package's command}
\newcommand{\leanquoteimports}{Other package's command}
\leanfile\leanfilequote
""")

    def test_existing_command_names_are_untouched(self):
        self.compile(r"""
\ifx\leanfile\expectedleanfile\else\errmessage{leanfile was changed}\fi
\ifx\leanfilequote\expectedleanfilequote\else\errmessage{leanfilequote was changed}\fi
\ifx\leanquotefile\expectedleanquotefile\else\errmessage{leanquotefile was changed}\fi
\ifx\leanquoteimports\expectedleanquoteimports\else\errmessage{leanquoteimports was changed}\fi
\leanquote[file=A.lean]{value}
""", before_package=r"""
\newcommand{\leanfile}{Existing command}
\let\expectedleanfile\leanfile
\newcommand{\leanfilequote}{Existing command}
\let\expectedleanfilequote\leanfilequote
\newcommand{\leanquotefile}{Existing command}
\let\expectedleanquotefile\leanquotefile
\newcommand{\leanquoteimports}{Existing command}
\let\expectedleanquoteimports\leanquoteimports
""")


if __name__ == "__main__":
    unittest.main()
