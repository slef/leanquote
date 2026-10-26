"""Exercise the listings rendering layer, independently of source extraction."""

import unittest

from tex_support import ENGINE, TexTestCase


class HighlightingTests(TexTestCase):
    @unittest.skipIf(ENGINE == "pdflatex", "Unicode-engine character table")
    def test_unicode_replacements_are_scoped_to_lean_style(self):
        _, output = self.compile_tex(
            {"A.lean": "def value : Nat := 1\n", "control.py": "value = 1\n"},
            r"""
\lstinputlisting[language=Python]{control.py}
\leanquote[file=A.lean]{value}
\lstinputlisting[language=Python]{control.py}
""",
            preamble=r"""
\makeatletter
\lst@AddToHook{SelectCharTable}{%
  \ifnum\catcode"03B1=13 \typeout{LEANQUOTE-UNICODE:active}%
  \else \typeout{LEANQUOTE-UNICODE:normal}\fi}
\makeatother
""",
        )
        self.assertEqual([line for line in output.splitlines() if line.startswith("LEANQUOTE-UNICODE:")],
                         ["LEANQUOTE-UNICODE:normal", "LEANQUOTE-UNICODE:active", "LEANQUOTE-UNICODE:normal"])


if __name__ == "__main__":
    unittest.main()
