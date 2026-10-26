"""Check resolved tcolorbox colors, option scope, and verification overlays."""

import re

from tex_support import TexTestCase


FILES = {"A.lean": "def value : Nat := 1\n"}
PREAMBLE = r"""
\leanquotesetup{file=A.lean,box=true,verify=false}
\tcbset{before upper={
  \convertcolorspec{named}{tcbcolback}{rgb}\BackRGB
  \convertcolorspec{named}{tcbcolframe}{rgb}\FrameRGB
  \typeout{LEANQUOTE-COLORS:\BackRGB;\FrameRGB}
}}
"""
GRAY = ((0.97, 0.97, 0.97), (0.55, 0.55, 0.55))
BLUE = ((0.97, 0.97, 1.0), (0.5, 0.5, 1.0))


class BoxOptionsTests(TexTestCase):
    def assert_colors(self, output, expected):
        actual = [
            tuple(tuple(float(component) for component in color.split(","))
                  for color in pair)
            for pair in re.findall(r"LEANQUOTE-COLORS:([\d.,]+);([\d.,]+)", output)
        ]
        self.assertEqual(len(actual), len(expected), output[-3000:])
        for actual_pair, expected_pair in zip(actual, expected):
            for actual_color, expected_color in zip(actual_pair, expected_pair):
                for actual_value, expected_value in zip(actual_color, expected_color):
                    self.assertAlmostEqual(actual_value, expected_value, delta=0.0001)

    def test_defaults_and_named_colors(self):
        _, output = self.compile_tex(FILES, r"""
\leanquote{value}
\definecolor{paper}{RGB}{245,250,255}
\definecolor{edge}{RGB}{32,64,128}
\leanquote[boxback=paper,boxframe=edge]{value}
\leanquote{value}
""", preamble=PREAMBLE)
        self.assert_colors(output, [
            GRAY, ((245/255, 250/255, 1), (32/255, 64/255, 128/255)), GRAY,
        ])

    def test_setup_per_quote_and_group_scope(self):
        _, output = self.compile_tex(FILES, r"""
\leanquote{value}
\leanquote[boxback=green!3]{value}
\leanquote{value}
\leanquote[boxframe=black]{value}
{\leanquotesetup{boxback=yellow!10,boxframe=green!50}\leanquote{value}}
\leanquote{value}
""", preamble=PREAMBLE + r"\leanquotesetup{boxback=blue!3,boxframe=blue!50}")
        self.assert_colors(output, [
            BLUE, ((0.97, 1, 0.97), BLUE[1]), BLUE,
            (BLUE[0], (0, 0, 0)), ((1, 1, 0.9), (0.5, 1, 0.5)), BLUE,
        ])

    def test_box_false_accepts_colors_without_creating_a_box(self):
        snippets, output = self.compile_tex(
            FILES, r"\leanquote[box=false,boxback=blue!3,boxframe=blue!50]{value}",
            preamble=PREAMBLE,
        )
        self.assertEqual(snippets, [FILES["A.lean"].strip()])
        self.assert_colors(output, [])

    def test_logo_and_verification_badge_with_custom_colors(self):
        # A placeholder image exercises the existing-file/logo branch without
        # adding binary fixtures or requiring the Lean trademark image.
        _, output = self.compile_tex(FILES, r"""
\leanquote[verify=true,logo=A.lean,boxback=blue!3,boxframe=blue!50]{value}
""", preamble=PREAMBLE + r"""
\RenewDocumentCommand\includegraphics{O{} m}{\typeout{LEANQUOTE-LOGO}\rule{8mm}{3mm}}
\let\OriginalBadge\leanquotebadge
\renewcommand{\leanquotebadge}[1]{\typeout{LEANQUOTE-BOX-BADGE:#1}\OriginalBadge{#1}}
""")
        self.assert_colors(output, [BLUE])
        self.assertIn("LEANQUOTE-LOGO", output)
        self.assertIn("LEANQUOTE-BOX-BADGE:UNVERIFIED", output)
