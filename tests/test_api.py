"""Run with python3 tests/test_api.py; select TeX via LEANQUOTE_TEX_ENGINE."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ENGINE = os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")
PACKAGE = Path(__file__).resolve().parents[1] / "latex" / "leanquote.sty"
VALUE = "def value : Nat := {}"
PROOF = "theorem truth : True := by\n  trivial"
HIDDEN_PROOF = "theorem truth : True := ..."


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
            (work / "Saved.leanquote").write_text(
                "@@leanquote-export 1\n@@begin value\n@@axioms\n"
                f"{VALUE.format(7)}\n@@end\n",
                encoding="utf-8",
            )
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
\leanquoteimports[file=B.lean]
\leanquote[file=B.lean]{:imports,value}
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
\leanquoteimports
\leanquoteimports[file=B.lean]
\leanquoteimports
{\leanquotefile{B.lean}\leanquote{value}}
\leanquote{value}
""", r"\leanquotefile[doc,proof=false,numbers=left]{A.lean}")
        documented_value = "/-- A value. -/\n" + VALUE.format(1)
        self.assertEqual(snippets, [
            documented_value, PROOF, "/-- A proof. -/\n" + HIDDEN_PROOF,
            "import Init", "import Lean", "import Init", VALUE.format(2), documented_value,
        ])

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
        for command in [r"\leanquote[file=A.lean]{value}", r"\leanquoteimports[file=A.lean]"]:
            with self.subTest(command=command):
                snippets, output = self.compile(command + r"\leanquote{value}", success=False)
                self.assertEqual(len(snippets), 1)
                self.assertIn("No Lean file specified", output)

    def test_missing_file_errors(self):
        for command in [r"\leanquote{value}", r"\leanquoteimports"]:
            with self.subTest(command=command):
                _, output = self.compile(command, success=False)
                self.assertIn("No Lean file specified", output)
                self.assertIn("file=...", output)
        _, output = self.compile(r"\leanquote[file=Missing.lean]{value}", success=False)
        self.assertIn("not found", output)
        _, output = self.compile(
            r"\leanquote[file={}]{value}", r"\leanquotefile{A.lean}", success=False,
        )
        self.assertIn("No Lean file specified", output)

    def test_removed_command_names_are_free(self):
        self.compile(r"""
\ifdefined\leanfile\errmessage{leanfile is still defined}\fi
\ifdefined\leanfilequote\errmessage{leanfilequote is still defined}\fi
\ifdefined\leanquotefrom\errmessage{leanquotefrom should not be defined}\fi
\newcommand{\leanfile}{Other package's command}
\newcommand{\leanfilequote}{Other package's command}
\leanfile\leanfilequote
""")

    def test_existing_command_names_are_untouched(self):
        self.compile(r"""
\ifx\leanfile\expectedleanfile\else\errmessage{leanfile was changed}\fi
\ifx\leanfilequote\expectedleanfilequote\else\errmessage{leanfilequote was changed}\fi
\leanquote[file=A.lean]{value}
""", before_package=r"""
\newcommand{\leanfile}{Existing command}
\let\expectedleanfile\leanfile
\newcommand{\leanfilequote}{Existing command}
\let\expectedleanfilequote\leanfilequote
""")


if __name__ == "__main__":
    unittest.main()
