"""Small end-to-end TeX runner shared by regression tests."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")


class TexTestCase(unittest.TestCase):
    def compile_tex(self, files, body, *, preamble="", fontenc=True, success=True):
        with tempfile.TemporaryDirectory(prefix="leanquote-regression-") as directory:
            work = Path(directory)
            shutil.copyfile(ROOT / "latex" / "leanquote.sty", work / "leanquote.sty")
            for filename, content in files.items():
                path = work / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            source = "\n".join([
                r"\documentclass{article}",
                r"\usepackage[T1]{fontenc}" if fontenc else "",
                r"\usepackage{leanquote}",
                r"\leanquotesetup{box=false}",
                r"\renewcommand{\leanquotebadgetext}[1]{\typeout{LEANQUOTE-BADGE:#1}}",
                preamble, r"\begin{document}", body, r"\end{document}", "",
            ])
            (work / "test.tex").write_text(source, encoding="utf-8")
            result = subprocess.run(
                [ENGINE, "-halt-on-error", "-interaction=nonstopmode", "test.tex"],
                cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=90,
            )
            self.assertEqual(result.returncode == 0, success, result.stdout[-6000:])
            snippets = sorted(
                work.glob("test-leanquote-*.lean"),
                key=lambda path: int(path.stem.rsplit("-", 1)[1]),
            )
            return [path.read_text(encoding="utf-8").strip() for path in snippets], result.stdout
