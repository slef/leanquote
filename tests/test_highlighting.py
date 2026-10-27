"""Exercise the listings rendering layer, independently of source extraction."""

import unittest
import re

from tex_support import ENGINE, TexTestCase


RENDER_LOG = r"""
\makeatletter
\lst@AddToHook{OutputBox}{%
  \convertcolorspec{named}{.}{rgb}\LQColor
  \typeout{LQ-RENDER:\expandafter\detokenize\expandafter{\the\lst@token}|\LQColor|\the\lst@lineno}}
\makeatother
"""


class HighlightingTests(TexTestCase):
    def render(self, code, *, body=None, options=""):
        _, output = self.compile_tex(
            {"Fixture.lean": code},
            body or r"\lstinputlisting[style=leanquote," + options + r"]{Fixture.lean}",
            preamble=RENDER_LOG,
        )
        return [(token.replace(r"\lst@nolig ", "").replace(r"\lst@um_ ", "_")
                 .replace(r"\lst@um", "").strip(),
                 tuple(float(v) for v in rgb.split(',')), int(line))
                for token, rgb, line in re.findall(
                    r"LQ-RENDER:([^\n]*?)\|([\d.,]+)\|(\d+)", output)]

    def assert_paint(self, rendered, word, line, color):
        colors = [rgb for token, rgb, number in rendered if token == word and number == line]
        self.assertTrue(colors, (word, line, rendered))
        for actual in colors:
            for component, expected in zip(actual, color):
                self.assertAlmostEqual(component, expected, delta=0.0001)

    def test_tex_escapes_preserve_following_code_colors(self):
        for annotation, options in [
            (r"(*@\textbf{note}@*)", r"escapeinside={(*@}{@*)}"),
            (r"!\textbf{note}!", "escapechar=!"),
            (r"$x+y$", "mathescape=true"),
            (r"(*@\textbf{first}@*) then (*@\emph{second}@*)", r"escapeinside={(*@}{@*)}"),
        ]:
            with self.subTest(options=options, annotation=annotation):
                code = "theorem sample : True /- " + annotation + " -/ := by trivial\n"
                rendered = self.render(code, options=options)
                self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
                self.assert_paint(rendered, 'trivial', 1, (136/255, 84/255, 150/255))
                self.assert_paint(rendered, 'True', 1, (38/255, 128/255, 89/255))
                quoted = self.render(code, body=r"\leanquote[file=Fixture.lean,verify=false," +
                                     options + r"]{sample}")
                self.assert_paint(quoted, 'by', 1, (41/255, 110/255, 166/255))
                self.assert_paint(quoted, 'trivial', 1, (136/255, 84/255, 150/255))

    def test_multiline_tex_escape_preserves_next_line_colors(self):
        code = 'theorem sample : True /- (*@\textbf{\nnote}@*) -/ := by trivial\n'
        rendered = self.render(code, options=r"escapeinside={(*@}{@*)}")
        self.assert_paint(rendered, 'by', 2, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'trivial', 2, (136/255, 84/255, 150/255))

    def test_environment_selection_preserves_omitted_lexical_context(self):
        code = "/- outer\ninner\nsorry Nat -/\ndef after : Nat := 1\n"
        for options in ["firstline=3", "firstline=3,mathescape"]:
            rendered = self.render("", body="\\begin{lstlisting}[style=leanquote," +
                options + "]\n" + code + "\\end{lstlisting}\n")
            self.assert_paint(rendered, "sorry", 3, (.4, .4, .4))
            self.assert_paint(rendered, "Nat", 3, (.4, .4, .4))
            self.assert_paint(rendered, "def", 4, (41/255, 110/255, 166/255))
        code = 'def raw : String := r#"first\n-- \\notARealCommand\nlast"#\ndef after : Nat := 1\n'
        rendered = self.render("", body=
            "\\begin{lstlisting}[style=leanquote,firstline=2,texcl=true]\n" +
            code + "\\end{lstlisting}\n")
        self.assert_paint(rendered, "notARealCommand", 2, (153/255, 77/255, 0))
        self.assert_paint(rendered, "def", 4, (41/255, 110/255, 166/255))

    def test_text_after_environment_close_keeps_tex_catcodes(self):
        for options in ["", ",mathescape", ",texcl=true"]:
            with self.subTest(options=options):
                _, output = self.compile_tex({}, "\\begin{lstlisting}[style=leanquote" +
                    options + "]\ndef value : Nat := 1\n" +
                    r"\end{lstlisting}\LQafter{After}" + "\n",
                    preamble=r"\newcommand{\LQafter}[1]{\typeout{LQ-AFTER:#1}\textbf{#1}}")
                self.assertIn("LQ-AFTER:After", output)

    def test_tex_escapes_in_environments_and_inline_listings(self):
        rendered = self.render("", body=r"""
\begin{lstlisting}[style=leanquote,escapeinside={(*@}{@*)}]
theorem sample : True /- (*@\textbf{note}@*) -/ := by trivial
\end{lstlisting}
""")
        self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'trivial', 1, (136/255, 84/255, 150/255))
        rendered = self.render("", body=r'\lstinline[style=leanquote,mathescape]!True /- $x+y$ -/ := by trivial!')
        self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'trivial', 1, (136/255, 84/255, 150/255))

    def test_indented_escaped_environments_gobble_only_source_characters(self):
        for annotation, options in [
            (r"(*@\textbf{note}@*)", r"escapeinside={(*@}{@*)}"),
            (r"$x+y$", "mathescape=true"),
        ]:
            with self.subTest(options=options):
                body = (r"\begin{lstlisting}[style=leanquote,gobble=2," + options + "]\n"
                        "  theorem sample : True /- " + annotation + " -/ := by trivial\n"
                        r"\end{lstlisting}" + "\n" +
                        r"\lstinputlisting[style=leanquote]{Fixture.lean}")
                rendered = self.render("def after : Nat := 1\n", body=body)
                self.assert_paint(rendered, 'theorem', 1, (41/255, 110/255, 166/255))
                self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
                self.assert_paint(rendered, 'trivial', 1, (136/255, 84/255, 150/255))
                self.assert_paint(rendered, 'def', 1, (41/255, 110/255, 166/255))

    def test_environment_indentation_preserves_literal_and_comment_colors(self):
        for indent in (2, 8, 12):
            for gobble in (0, indent):
                with self.subTest(indent=indent, gobble=gobble):
                    code = ''.join(' ' * indent + 'def ' + name +
                        ' : String := "Nat sorry" -- comment\n' for name in ('first', 'second'))
                    rendered = self.render('', body=
                        '\\begin{lstlisting}[style=leanquote,gobble=' + str(gobble) + ']\n' +
                        code + '\\end{lstlisting}\n')
                    for line in (1, 2):
                        self.assert_paint(rendered, 'def', line, (41/255, 110/255, 166/255))
                        self.assert_paint(rendered, 'String', line, (38/255, 128/255, 89/255))
                        self.assert_paint(rendered, '=', line, (0, 0, 0))
                        self.assert_paint(rendered, 'Nat', line, (153/255, 77/255, 0))
                        self.assert_paint(rendered, 'sorry', line, (153/255, 77/255, 0))
                        self.assert_paint(rendered, 'comment', line, (.4, .4, .4))

    def test_multiline_escaped_environment_keeps_colors_and_scope(self):
        body = r"""
\begin{lstlisting}[style=leanquote,escapeinside={(*@}{@*)}]
theorem αsample : True /- (*@\textbf{
note}@*) -/ := by trivial
\end{lstlisting}
\lstinputlisting[style=leanquote]{Fixture.lean}
"""
        rendered = self.render('def after : Nat := 1\n', body=body)
        self.assert_paint(rendered, 'by', 2, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'trivial', 2, (136/255, 84/255, 150/255))
        self.assert_paint(rendered, 'def', 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'Nat', 1, (38/255, 128/255, 89/255))

    def test_literate_replacement_widths_preserve_following_colors(self):
        code = ("theorem arrows : True -> True -> True -> True -> True -> True /- trailing -/ := by\n"
                "  intros a b c d e\n  exact a\n"
                'def text : String := "=>" -- afterString\n')
        options = r"literate={->}{{$\to$}}1 {=>}{{$\mapsto$}}4"
        rendered = self.render(code, options=options)
        self.assert_paint(rendered, 'trailing', 1, (.4, .4, .4))
        self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'afterString', 4, (.4, .4, .4))
        rendered = self.render(code, body=r"\leanquote[file=Fixture.lean,verify=false," +
                               options + r"]{arrows,text}")
        self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'afterString', 5, (.4, .4, .4))

    def test_zero_width_replacement_and_tabs_keep_source_alignment(self):
        rendered = self.render('def text : String := "xx" -- afterZero\n'
                               "theorem arrow : True /- ->\tcomment -/ := by trivial\n",
                               options=r"literate={xx}{}0 {->}{{$\to$}}1")
        self.assert_paint(rendered, 'afterZero', 1, (.4, .4, .4))
        self.assert_paint(rendered, 'comment', 2, (.4, .4, .4))
        self.assert_paint(rendered, 'by', 2, (41/255, 110/255, 166/255))

    def test_starred_literate_preserves_literals_and_nested_comments(self):
        code = ('def text : String := "->"\n'
                "theorem arrow : True -> True := by intro h; exact h\n"
                "/- -> /- -> -/ -> -/\n"
                "def raw : String := r#\"->\"# -- ->\n")
        options = r"literate=*{->}{{\typeout{LQ-REPLACED}$\to$}}1"
        for body in [
            r"\lstinputlisting[style=leanquote," + options + "]{Fixture.lean}",
            "\\begin{lstlisting}[style=leanquote," + options + "]\n" + code + "\\end{lstlisting}",
            r"\leanquote[file=Fixture.lean,verify=false," + options + "]{text,arrow,raw}",
        ]:
            with self.subTest(body=body):
                _, output = self.compile_tex({"Fixture.lean": code}, body)
                self.assertEqual(output.count("LQ-REPLACED"), 1, output[-2000:])

    def test_texcl_executes_only_real_line_comments(self):
        code = ('def text : String := "-- \\\\LQannotation"\n'
                '/- -- \\LQannotation /- nested -/ -/\n'
                "def value : Nat := 1 -- \\LQannotation\n"
                "def after : Nat := 2\n")
        for body in [
            r"\lstinputlisting[style=leanquote,texcl=true]{Fixture.lean}",
            "\\begin{lstlisting}[style=leanquote,texcl=true,gobble=2]\n" +
            "".join("  " + line + "\n" for line in code.splitlines()) + "\\end{lstlisting}",
            r"\leanquote[file=Fixture.lean,verify=false,texcl=true]{text,value,after}",
        ]:
            with self.subTest(body=body):
                _, output = self.compile_tex({"Fixture.lean": code}, body,
                    preamble=r"\newcommand{\LQannotation}{\typeout{LQ-TEXCL}\textbf{annotation}}")
                self.assertEqual(output.count("LQ-TEXCL"), 1, output[-2000:])
        rendered = self.render(code.replace(r"\LQannotation", r"\textbf{annotation}"),
                               options="texcl=true")
        self.assert_paint(rendered, 'def', 4, (41/255, 110/255, 166/255))
        _, output = self.compile_tex({"Fixture.lean": "// \\LQannotation\n"},
            r"\lstinputlisting[style=leanquote,morecomment={[l]{//}},texcl=true]{Fixture.lean}",
            preamble=r"\newcommand{\LQannotation}{\typeout{LQ-TEXCL}\textbf{annotation}}")
        self.assertEqual(output.count("LQ-TEXCL"), 1)

    def test_visible_string_spaces_respect_lexical_boundaries_and_scope(self):
        code = ('def text : String := "a  b"\n'
                'def raw : String := r#"a b"#\n'
                "def character : Char := ' '\n"
                'def interpolated : String := s!"a {Nat.succ 1} b"\n'
                '-- a b\n'
                'def after : Nat := 1\n')
        log = r"""
\makeatletter
\lst@AddToHook{OutputBox}{\ifx\lst@outputspace\lst@visiblespace
  \typeout{LQ-VISIBLE-SPACE}\fi}
\makeatother
"""
        for options in ["showstringspaces=true", "showstringspaces=true,keepspaces=false"]:
            for body in [
                r"\lstinputlisting[style=leanquote," + options + "]{Fixture.lean}",
                "\\begin{lstlisting}[style=leanquote," + options + "]\n" + code + "\\end{lstlisting}",
                r"\leanquote[file=Fixture.lean,verify=false," + options + "]{text,raw,character,interpolated,after}",
            ]:
                with self.subTest(options=options, body=body):
                    _, output = self.compile_tex({"Fixture.lean": code}, body + "\n" +
                        r"\lstinputlisting[style=leanquote,showstringspaces=false]{Fixture.lean}",
                        preamble=log)
                    self.assertEqual(output.count("LQ-VISIBLE-SPACE"), 6, output[-2000:])

    def test_trailing_literal_spaces_reach_listings_output(self):
        code = 'def text : String := "first \n  \nlast"\n'
        log = r"""
\makeatletter
\lst@AddToHook{OutputBox}{\ifx\lst@outputspace\lst@visiblespace
  \typeout{LQ-VISIBLE-SPACE}\fi}
\makeatother
"""
        for body, count in [
            (r"\lstinputlisting[style=leanquote,showstringspaces=true]{Fixture.lean}", 3),
            (r"\lstinputlisting[style=leanquote,showstringspaces=true,lastline=1]{Fixture.lean}", 1),
            (r"\lstinputlisting[style=leanquote,showstringspaces=true,firstline=2,lastline=2]{Fixture.lean}", 2),
            (r"\leanquote[file=Fixture.lean,verify=false,showstringspaces=true]{text}", 3),
        ]:
            with self.subTest(body=body):
                _, output = self.compile_tex({"Fixture.lean": code}, body + "\n" +
                    r"\lstinputlisting[style=leanquote,showstringspaces=false]{Fixture.lean}",
                    preamble=log)
                self.assertEqual(output.count("LQ-VISIBLE-SPACE"), count, output[-2000:])

    def test_literate_offsets_survive_tex_escapes_and_reset_for_following_listings(self):
        code = (r"theorem arrows : True -> True -> True -> True -> True -> True /- "
                r"(*@\textbf{note}@*)"
                " -/ := by intros a b c d e; exact a\n")
        body = r"""
\lstinputlisting[style=leanquote,escapeinside={(*@}{@*)},literate={->}{{$\to$}}1]{Fixture.lean}
\begin{lstlisting}[style=leanquote]
def control : String := "sorry" -- afterControl
\end{lstlisting}
"""
        rendered = self.render(code, body=body)
        self.assert_paint(rendered, 'by', 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'exact', 1, (136/255, 84/255, 150/255))
        self.assert_paint(rendered, 'sorry', 1, (153/255, 77/255, 0))
        self.assert_paint(rendered, 'afterControl', 1, (.4, .4, .4))

    def test_raw_strings_and_hash_counts_keep_comment_text_literal(self):
        rendered = self.render('''def raw : String := r##"first "# sorry Nat /- --
last"##
def afterRaw : Nat := 1
''', options=r"stringstyle=\color{orange}")
        self.assert_paint(rendered, 'sorry', 1, (1, .5, 0))
        self.assert_paint(rendered, 'Nat', 1, (1, .5, 0))
        self.assert_paint(rendered, 'last', 2, (1, .5, 0))
        self.assert_paint(rendered, 'def', 3, (41/255, 110/255, 166/255))

    def test_interpolation_distinguishes_nested_strings_and_expressions(self):
        rendered = self.render('''def text : String := s!"inner {"first sorry Nat"} tail"
def expression : String := s!"value {Nat.succ 1}"
def nested : String := s!"outer {s!"inner {Nat.succ 1}"} tail"
''', options=r"stringstyle=\color{orange}")
        self.assert_paint(rendered, 'sorry', 1, (1, .5, 0))
        self.assert_paint(rendered, 'Nat', 1, (1, .5, 0))
        self.assert_paint(rendered, 'Nat', 2, (38/255, 128/255, 89/255))
        self.assert_paint(rendered, 'Nat', 3, (38/255, 128/255, 89/255))

    def test_builtin_message_interpolation_and_plain_reference_strings(self):
        rendered = self.render(
            'import Lean\nopen Lean\n'
            'def message : CoreM Unit := do\n'
            '  dbg_trace "literal {Nat.succ 1} sorry"\n'
            '  throwErrorAt (Syntax.mkStrLit "{ ordinary") "literal {Nat.succ 1} sorry"\n'
            'def qualified : CoreM Unit := Lean.throwError "{ literal"\n'
            'def after : Nat := 1\n')
        for line in [4, 5]:
            self.assert_paint(rendered, 'Nat', line, (38/255, 128/255, 89/255))
            self.assert_paint(rendered, 'sorry', line, (153/255, 77/255, 0))
        self.assert_paint(rendered, 'ordinary', 5, (153/255, 77/255, 0))
        self.assert_paint(rendered, 'literal', 6, (153/255, 77/255, 0))
        self.assert_paint(rendered, 'def', 7, (41/255, 110/255, 166/255))

    def test_known_interpolators_and_ordinary_bang_functions(self):
        rendered = self.render(
            'import Lean\nopen String\n'
            'def s := s!"{Nat.succ 1}"\n'
            'def m := m!"{Nat.succ 1}"\n'
            'def f := f!"{Nat.succ 1}"\n'
            'def n := String.toNat! "{ Nat"\n'
            'def u := toNat! "{ Nat"\n'
            'def after := 1\n')
        for line in [3, 4, 5]:
            self.assert_paint(rendered, "Nat", line, (38/255, 128/255, 89/255))
        for line in [6, 7]:
            self.assert_paint(rendered, "Nat", line, (153/255, 77/255, 0))
        self.assert_paint(rendered, "def", 8, (41/255, 110/255, 166/255))

    def test_string_gaps_preserve_interpolation_and_following_colors(self):
        code = ('def text : String := s!"first' + chr(92) +
                '\n{"hello\ndef phantom : Nat := 99\nlast"}"\n'
                'def after : Nat := 1\n'
                'def close : String := "first' + chr(92) + '\n"\n'
                'def last : Nat := 2\n')
        rendered = self.render(code)
        self.assert_paint(rendered, 'def', 3, (153/255, 77/255, 0))
        self.assert_paint(rendered, 'Nat', 3, (153/255, 77/255, 0))
        for line in (5, 8):
            self.assert_paint(rendered, 'def', line, (41/255, 110/255, 166/255))

    def test_character_literals_touching_operators_keep_lexical_context(self):
        code = ('def character : Unit → Char := fun _ =>'+chr(39)+chr(34)+chr(39)+'\n'
                "def αname' : Nat := 1\n"
                "theorem equation : (c : Char) → c = c\n"
                "  |'a' => rfl\n"
                "  | c => rfl\n"
                "def afterCharacter : Nat := 2\n")
        rendered = self.render(code, options=r"stringstyle=\color{orange}")
        self.assert_paint(rendered, '"', 1, (1, .5, 0))
        literal = [(token, color) for token, color, line in rendered
                   if line == 4 and token.replace(" ", "").strip("'") == "a"]
        self.assertTrue(literal, rendered)
        self.assertTrue(all(color == (1, .5, 0) for _, color in literal), literal)
        self.assert_paint(rendered, 'def', 6, (41/255, 110/255, 166/255))

    def test_character_literals_do_not_change_following_declarations(self):
        rendered = self.render("def quote : Char := '\"'\ndef afterCharacter : Nat := 1\n",
                               options=r"stringstyle=\color{orange}")
        self.assert_paint(rendered, '"', 1, (1, .5, 0))
        self.assert_paint(rendered, 'def', 2, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'Nat', 2, (38/255, 128/255, 89/255))

    def test_escaped_names_protect_keywords_and_comment_delimiters(self):
        rendered = self.render('''def «theorem» : Nat := 1
def «sorry Nat» : Nat := 2
def «x/-y» : Nat := 3
def afterName : Nat := 4
def «first
sorry /- Nat
last» : Nat := 5
def afterMultiline : Nat := 6
''')
        self.assert_paint(rendered, 'theorem', 1, (0, 0, 0))
        self.assert_paint(rendered, 'sorry', 2, (0, 0, 0))
        self.assert_paint(rendered, 'def', 4, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'sorry', 6, (0, 0, 0))
        self.assert_paint(rendered, 'def', 8, (41/255, 110/255, 166/255))

    def test_identifier_boundaries_include_apostrophes_and_unicode(self):
        rendered = self.render("def theorem' := 1\ndef αNat := 2\ndef Natα := 3\ndef Nat₁ := 4\n")
        self.assert_paint(rendered, "theorem'", 1, (0, 0, 0))
        for line in (2, 3, 4):
            self.assert_paint(rendered, 'Nat', line, (0, 0, 0))

    def test_nested_comments_and_ordinary_escaped_strings(self):
        rendered = self.render(r'''/- outer /- sorry -/ Nat -/
def text := "escaped \" sorry Nat \\ /- --"
def after : Nat := 1
''', options=r"stringstyle=\color{orange}")
        self.assert_paint(rendered, 'sorry', 1, (.4, .4, .4))
        self.assert_paint(rendered, 'Nat', 1, (.4, .4, .4))
        self.assert_paint(rendered, 'sorry', 2, (1, .5, 0))
        self.assert_paint(rendered, 'Nat', 2, (1, .5, 0))
        self.assert_paint(rendered, 'def', 3, (41/255, 110/255, 166/255))

    def test_core_vocabulary_and_custom_keyword_boundaries(self):
        rendered = self.render('''forall for unless while try catch mut local export
IO simp_all simp? repeat' theorem' Nat'
ProjectType
''', options="morekeywords={[2]{ProjectType}}")
        for word in ('forall', 'for', 'unless', 'while', 'try', 'catch', 'mut', 'local', 'export'):
            self.assert_paint(rendered, word, 1, (41/255, 110/255, 166/255))
        self.assert_paint(rendered, 'IO', 2, (38/255, 128/255, 89/255))
        for word in ('simp_all', 'simp?', "repeat'"):
            self.assert_paint(rendered, word, 2, (136/255, 84/255, 150/255))
        self.assert_paint(rendered, "theorem'", 2, (0, 0, 0))
        self.assert_paint(rendered, "Nat'", 2, (0, 0, 0))
        self.assert_paint(rendered, 'ProjectType', 3, (38/255, 128/255, 89/255))
        rendered = self.render('def thing : ProjectType := sorry\n', body=r'''
\leanquotesetup{morekeywords=[2]{ProjectType}}
\leanquote[file=Fixture.lean,verify=false]{thing}
''')
        self.assert_paint(rendered, 'ProjectType', 1, (38/255, 128/255, 89/255))

    def test_default_string_color_can_be_overridden_or_disabled(self):
        for options, expected in [('', (.6, 77/255, 0)),
                                  (r'stringstyle=\color{blue}', (0, 0, 1)),
                                  ('stringstyle={}', (0, 0, 0))]:
            with self.subTest(options=options):
                rendered = self.render('def text := "sorry"\n', options=options)
                self.assert_paint(rendered, 'sorry', 1, expected)

    def test_qualified_names_keep_only_head_highlighting(self):
        rendered = self.render('Set.univ x.Set Mathlib.MeasureTheory.Measure\n')
        sets = [rgb for token, rgb, _ in rendered if token == 'Set']
        self.assertEqual(len(sets), 2)
        self.assertAlmostEqual(sets[0][1], 128/255, delta=.0001)
        self.assertEqual(sets[1], (0, 0, 0))
        self.assert_paint(rendered, 'Measure', 1, (0, 0, 0))

    def test_listing_environment_uses_same_lexer(self):
        rendered = self.render('', body=r'''
\begin{lstlisting}[style=leanquote,stringstyle=\color{orange}]
def text : String := r#"first " sorry /- " last"#
def after : Nat := 1
\end{lstlisting}
''')
        self.assert_paint(rendered, 'sorry', 1, (1, .5, 0))
        self.assert_paint(rendered, 'def', 2, (41/255, 110/255, 166/255))

    def test_inline_listings_use_same_lexer(self):
        for body in [
            r'\lstinline[style=leanquote,stringstyle=\color{orange}]!r#"first " sorry /- " last"#!',
            r'\lstinline[style=leanquote,stringstyle=\color{orange}]{r#"first " sorry /- " last"#}',
        ]:
            with self.subTest(body=body):
                rendered = self.render('', body=body)
                self.assert_paint(rendered, 'sorry', 1, (1, .5, 0))

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

    @unittest.skipIf(ENGINE == "pdflatex", "Unicode-engine active character definitions")
    def test_unicode_body_definition_survives_package_and_listing(self):
        _, output = self.compile_tex(
            {"A.lean": "def αvalue : Nat := 1\n"},
            r"Before: α. \leanquote[file=A.lean,verify=false]{αvalue} After: α.",
            before_package=r"""
\usepackage{newunicodechar}
\newunicodechar{α}{\typeout{LQ-BODY-ALPHA}\ensuremath{\alpha}}
""",
        )
        self.assertEqual(output.count("LQ-BODY-ALPHA"), 2, output)

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
\lstset{style=leanquote}
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
