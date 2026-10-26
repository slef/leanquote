"""Exercise the listings rendering layer, independently of source extraction."""

import unittest
import re

from tex_support import ENGINE, TexTestCase


RENDER_LOG = r"""
\makeatletter
\lst@AddToHook{OutputBox}{%
  \extractcolorspec{.}\LQColor
  \typeout{LQ-RENDER:\expandafter\detokenize\expandafter{\the\lst@token}|\LQColor}}
\makeatother
"""


class HighlightingTests(TexTestCase):
    def test_unicode_replacements_follow_buffered_ascii(self):
        _, output = self.compile_tex(
            {"A.lean": "def Natα : Nat := 1\ndef Nat₁ : Nat := 2\n"},
            r"\leanquote[file=A.lean,verify=false]{Natα,Nat₁}", preamble=RENDER_LOG,
        )
        tokens = re.findall(r"LQ-RENDER:(.*?)\|", output)
        # Inspect actual output boxes, not the extracted source: both Unicode
        # replacements must follow the preceding identifier in the PDF stream.
        math_positions = [i for i, token in enumerate(tokens)
                          if "alpha" in token or "_1" in token]
        self.assertEqual(len(math_positions), 2, tokens)
        for position in math_positions:
            self.assertEqual(tokens[position - 1], "Nat", tokens)

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
