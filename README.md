# leanquote

Typeset Lean declarations in a LaTeX paper **by name**, read directly from the Lean source
at LaTeX compile time.

```latex
\usepackage{leanquote}
\leanquotesetup{file=Abstract.lean}
...
$P$ \emph{tiles} $\mathbb{Z}^3$ if some set $T$ of translations puts every point in exactly
one translate $t + P$:
\leanquote{Tiles}
```

The prose stays in the paper, written as usual; the code is never retyped or pasted. If a name
is misspelled, LaTeX stops with an error. If an automatically selected export is stale,
LaTeX warns and reads the current source instead. An explicitly selected export is a snapshot;
if its source has changed, the quote is marked UNVERIFIED.

It was written for papers that present a short, human-readable `Abstract.lean` (definitions and
main theorem statements of a formalization, proved through a bridge to the full development),
and can quote other Lean 4 files too; unusual layouts need the optional exporter.

## Usage

Put `latex/leanquote.sty` where LaTeX can find it (next to your paper, or in `TEXINPUTS`), then:

```latex
\usepackage{leanquote}
\leanquotesetup{project=../lean/}           % root of your Lake project
...
\leanquotesetup{file=TranslationTiling/Abstract.lean} % default file for following quotes
\leanquote{Point, Prototile}
\leanquote[doc]{Tiles}                      % with its doc comment
\leanquote[proof=false]{main_theorem}       % statement only, proof shown as := ...
\leanquote[file=Other/File.lean]{foo}       % one-off quote from another file
\leanquote[imports]{Point, Prototile}      % imports, then declarations in one listing
\leanquote[imports]{}                     % only the import block of the current file
\leanquote[imports,file=Other/File.lean]{} % imports from another file
```

These are the two main commands: `\leanquotesetup{options}` sets defaults for following
quotes, and `\leanquote[options]{names}` quotes declarations from the selected file.
Setup works in the preamble and follows normal TeX group scope. A per-call `file=...`
selects a file without changing the default, and works without preceding setup.
A file must be supplied by one of these methods.
With `project=../lean/`, `.lean` paths are relative to that directory; include its trailing
slash. Without `project`, paths are relative to the LaTeX working directory. Explicit
`.leanquote` paths and the `olean`, `source`, and `logo` options are used as supplied,
without a `project` prefix.

The Boolean `imports` option prepends the import block once, before the named declarations,
in the same listing. `\leanquote[imports]{}` quotes only that block: the `module`, `prelude`, and
`[public|private|meta] import` lines at the top of the file, with comments omitted.
It defaults to false; bare `imports` means `imports=true`. An enabled setup default can
be overridden with `imports=false` for one quote. Names such as `import` and `imports`
remain ordinary declaration lookups.

No step on the Lean side beyond your usual `lake build`; LaTeX does not run Lean or require
shell escape:

- **Finding a declaration.** It starts at its `def`/`theorem`/`abbrev`/... line in column 0
  (with any attribute lines, and the doc comment if `doc` is set), and continues while lines are
  blank, indented, or start with `|`, `termination_by`, `decreasing_by` or `deriving`. This
  matches the standard Lean layout. Names may be short (`Tiles`) or qualified (`TranslationTiling.Abstract.Tiles`); a
  qualified name matches a declaration inside the corresponding `namespace`. The requested name
  must be the full name or a dotted suffix of it, including escaped components such as
  `«A B».foo`. Nested comments and strings are skipped when
  finding declarations, and namespace/section scope is tracked. An unknown name is an error,
  an ambiguous short name a warning, with the first match used.
- **What has Lean checked?** Quotes get a red mark in the corner of their box
  (and a warning in the log) when they are not known to be fully checked:
  - **UNVERIFIED**: the `.lean` file is newer than its compiled `.olean`, or its last `lake build`
    failed; an export's source/build is stale or its verification metadata is missing;
    with `verify=true`, also when there is no compiled file;
  - **USES SORRY**: the declaration depends on `sorry`, anywhere in its dependencies (needs an export);
  - **SORRY IN FILE**: Lake's build log reports a `sorry` in the file (without an export);
  - **EXTRA AXIOMS**: the declaration depends on axioms beyond `propext`, `Classical.choice`,
    `Quot.sound`, e.g. via `native_decide` (needs an export).

  When a compiled file is available, its timestamp is compared with the source. A current v2
  export also checks axiom dependencies against its recorded Lake build fingerprint; rebuilding
  an imported proof invalidates that fingerprint even if the quoted source is unchanged.
  Without an export, a `sorry` in an imported file is not seen.
  `verify=false` disables verification marks and axiom/build checks.

### Publishing: arXiv, CI, Overleaf

ArXiv.org, CI builds and online editors compile the LaTeX themselves, usually without building Lean.
Include the `.lean` files and `leanquote.sty` in the upload. Without compiled files or exports,
the default `verify=auto` does not mark quotes UNVERIFIED. Do the check where Lean is built:
run `lake build`, compile the paper locally, check for leanquote warnings and UNVERIFIED marks,
then upload. If CI builds Lean, use `verify=true` there to catch missing compiled files too.
Portable exports can still report USES SORRY or EXTRA AXIOMS without a local Lean build.

### Optional: exact boundaries and axioms with `leanquote-export`

If you want Lean itself to say where each declaration starts and ends, run, from the root of the
Lake project:

```sh
path/to/leanquote/leanquote-export TranslationTiling.Abstract [MORE.Modules ...]
```

This builds each module and writes `.lake/build/leanquote/TranslationTiling/Abstract.leanquote`
(inside the build directory, so not tracked by git). From then on, `\leanquote` finds it
automatically and uses Lean's exact declaration ranges, and the axioms each declaration depends
on (for the USES SORRY and EXTRA AXIOMS marks); nothing else changes in the paper.
The exporter asks Lake for the actual source and compiled-file paths, including custom source
directories. It records the build fingerprint as well as the source text.
The v2 format rejects control characters in metadata (including names and paths),
whitespace inside axiom names, and bare carriage returns in source. LF and CRLF are supported.
If `Abstract.lean` is edited after the export, LaTeX warns and reads the `.lean` file
directly, so quotes of a `.lean` file show its current code. An export placed next to the
`.lean` file (`Abstract.leanquote`) is also found. An export can be given explicitly as
`\leanquote[file=Abstract.leanquote]{...}`. An explicit export deliberately shows its recorded
snapshot. With verification enabled, changed source or a different local build produces
an UNVERIFIED mark. With no local build, `verify=auto` can use a v2 snapshot's recorded
axioms; `verify=true` marks it unverified.
Older v1 exports remain readable but are marked UNVERIFIED until regenerated.
Nothing is added to your Lean project.
The exporter requires modules configured in a Lake `lean_lib`, with source and build
paths inside the project. Its output directory mirrors each module's actual source path.

For an explicit export, `root=../lean/` prefixes the source path recorded in the export;
`source=../lean/Other.lean` overrides it with a complete path. Compiled artifact paths
recorded in the export are relative to `project`, or to `root` if `project` is unset.
These options locate files for verification; they do not change the snapshot shown.

## Options

Set per quote (`\leanquote[doc]{...}`), or set defaults for the document or current group
with `\leanquotesetup{...}`. Per-call options override defaults for that quote only.

| Option | Default | Meaning |
|---|---|---|
| `file=<path>` | current file | select the file to quote; per-call overrides leave the default unchanged |
| `doc` | false | also show each declaration's doc comment |
| `imports` | false | prepend the import block once; an empty name list quotes only imports |
| `proof` | true | with `proof=false`, theorem and lemma proofs (assignment or equation style) become `:= ...`; definitions keep their bodies |
| `box` | true | put the listing in a light box (`leanquotebox`) |
| `boxback=<color>` | `black!3` | background color of the box |
| `boxframe=<color>` | `black!45` | border color of the box and logo outline |
| `logo=<file>` | none | image in the box's top-right corner; see “Boxes and logos” below |
| `style=<name>` | `leanquote` | listings style; the default handles common Lean Unicode on all three engines |
| `basicstyle=<commands>` | from style | font commands for the code; overrides the selected listings style's font |
| `stringstyle=<commands>` | from style | font/color commands for string and character literals; default `\color{leanquotestring}` |
| `project=<dir>/` | empty | root of the Lake project; `.lean` paths are relative to it |
| `olean=<file>` | | the compiled file to compare with, if not at the standard place |
| `verify=<mode>` | `auto` | `auto`: check available source/build/export metadata; `true`: also mark missing compiled files UNVERIFIED; `false`: disable verification (old name: `check`) |
| `root=<dir>/` | empty | prefix for an explicit export's recorded source path |
| `source=<path>` | from export | complete source path overriding an explicit export's recorded path |
| any other key | | passed to listings (e.g. `numbers=left`); setup settings follow the same group scope |

## Lean listing format

### Code font

`basicstyle` is a listings option forwarded by leanquote. The default `leanquote` style
uses `\ttfamily\small`. Include both the font family and size when overriding it:

```latex
\leanquotesetup{basicstyle=\ttfamily\footnotesize} % default for following quotes
\leanquote[basicstyle=\ttfamily\small]{Tiles}     % override for one quote
```

For an explicit point size, use `\ttfamily\fontsize{9.5}{11.5}\selectfont`;
the arguments specify font size and baseline spacing. The manual uses this setting
to fit its long example lines.

### Boxes and logos

With `box=true` (the default), set the background with `boxback` and the border with
`boxframe`. Both accept xcolor names and expressions such as `blue!3`:

```latex
\leanquotesetup{boxback=blue!3,boxframe=blue!50}
\leanquote[boxback=green!3,boxframe=green!50]{Tiles}
```

Setup sets the defaults for later quotes in the current TeX group. Per-call settings
affect only that quote, so no surrounding group is needed. These options apply to
leanquote boxes; other tcolorboxes keep their own settings. `boxframe` also sets the
logo outline color; verification badges retain their red background.

Set `logo=<file>` to add an image at the top-right corner, followed by `\leanquotelogomark`,
a small TM as required by the [Lean trademark policy](https://lean-lang.org/trademark-policy).
The Lean logo is not included. When using it, put `\leanquotetrademark` once in the paper,
for example in the acknowledgments. For other logos, remove the TM with
`\renewcommand{\leanquotelogomark}{}`.

### Syntax highlighting and Unicode

The default style colors keywords (blue), sorts and common Lean/Mathlib types such as `Nat`,
`Fin`, `Set`, `List`, `Finset`, `Real` (green), common tactics (purple) and `sorry` (red). A word right after a dot is not colored, so `Set`
is green in `Set.univ` but import paths like `Mathlib.MeasureTheory.Measure.Lebesgue.Basic` stay
plain. Add your own types with `\leanquotesetup{morekeywords=[2]{Prototile, Point}}` (`[3]` for tactics);
the colors are `leanquotekeyword`, `leanquotetype` and `leanquotetactic`.
Strings and character literals use the brown `leanquotestring` color. Raw strings,
interpolation expressions, nested comments, and escaped identifiers are recognized separately.
Change the literal style with `\leanquotesetup{stringstyle=\color{brown}}`, or use
`stringstyle={}` for plain literals. These settings can also be passed to one quote.

The default style typesets about a hundred of Lean's Unicode symbols as math, under
pdfLaTeX, LuaLaTeX and XeLaTeX. Others can be added with `literate` (pdfLaTeX) or a
monospace font that has them (LuaLaTeX, XeLaTeX).

## Texlish

[Texlish](https://texlish.org) passes LaTeX commands through, so `::use leanquote` works as is,
and the one-argument forms read naturally:

```
\leanquotesetup: file=Abstract.lean
\leanquote: main_theorem
```

(With an option, use braces: `\leanquote[doc]{main_theorem}`; Texlish's colon form does not
take an optional argument.)
Use `\leanquote[imports]{}` for imports only.

## Example

`example/example.tex` typesets the abstract of
[translation-tiling-paper](https://github.com/edemaine/translation-tiling-paper) from a copy of
its `Abstract.lean` (and, once, from the optional export `example/Abstract.leanquote`):

```sh
cd example && TEXINPUTS=../latex: pdflatex example.tex
```

## What is and is not guaranteed

- Quotes of a `.lean` file show its current text, using layout rules unless an up-to-date export
  supplies exact boundaries. Explicit `.leanquote` inputs show snapshots, with a warning and
  UNVERIFIED mark when a changed source or local build is detected.
- Local build checks rely on file timestamps and Lake's recorded build fingerprints; they are
  not a substitute for running `lake build`. Without build artifacts, `verify=auto` cannot
  establish the status of a local build; use `verify=true` to mark this case.
  LaTeX never compiles Lean itself.
- Quotes work in figure bodies, ordinary macro arguments, and footnotes; this does not imply
  support for complete listings in moving arguments such as caption or heading text.

Each listing writes a generated `<jobname>-leanquote-<n>.lean` file. These files are not
deleted automatically; you might add `*-leanquote-*.lean` to `.gitignore`.

Tested with pdfLaTeX, LuaLaTeX and XeLaTeX from TeX Live 2025, and with Lean v4.26.0,
v4.29.1, v4.31.0 and v4.35.0 (exporter).

## Documentation

Download the manual PDF from [GitHub releases](https://github.com/slef/leanquote/releases),
or find it at `doc/leanquote-doc.pdf` in the CTAN archive.
Generated PDFs are distributed as build/release assets rather than tracked in Git.

## Development and releases

From a Git checkout or an extracted CTAN archive, `./make-ctan.sh` builds the manual
from `doc/leanquote-doc.tex` and writes `leanquote.zip`. It requires a POSIX shell
(Cygwin on Windows), pdfLaTeX, zip and unzip.

From a Git checkout, run all regression tests with:

```sh
python3 -m unittest discover -s tests -v
```

Tests require Python 3, the packaging tools above, and Lean/Lake via elan for exporter
tests. Set `LEANQUOTE_TEX_ENGINE=lualatex` or `LEANQUOTE_TEX_ENGINE=xelatex` to select
another engine; pdfLaTeX is still needed to build the manual. Set `ELAN_TOOLCHAIN`
to select a Lean version, for example `leanprover/lean4:v4.35.0`.

CI runs discovered tests under all three TeX engines and Lean v4.28.0/v4.35.0, including
source-only packaging and the extracted example. Each run uploads the built manual PDF
and CTAN ZIP as the `leanquote-distribution` artifact. Publishing a GitHub release runs
the same checks and attaches both files to that release using the built-in GitHub token.

## Related tools

As far as we know, no other tool quotes Lean declarations by name in an ordinary LaTeX document
or checks quoted code against the compiled module. Related work (details in the manual):

- **Marker-based inclusion in LaTeX:** [catchfilebetweentags](https://ctan.org/pkg/catchfilebetweentags),
  [listings](https://ctan.org/pkg/listings) line ranges, [piton](https://ctan.org/pkg/piton),
  [tagsnip](https://ctan.org/pkg/tagsnip), [minted](https://ctan.org/pkg/minted) `rangeregex`
  (with Pygments' Lean 4 lexer). Any language; markers or patterns in the source.
- **Lean-native documents:** [Verso](https://github.com/leanprover/verso) and
  [SubVerso](https://github.com/leanprover/subverso) include anchored Lean code in documents
  written in Verso, with Lean's highlighting and mismatch errors.
- **Blueprints:** [leanblueprint](https://github.com/PatrickMassot/leanblueprint) (`\lean{}`,
  `checkdecls`) and [LeanArchitect](https://github.com/hanwenzhu/LeanArchitect) link LaTeX and
  Lean by name without quoting code; they combine with leanquote.
- **Other proof assistants:** Isabelle document preparation and
  [cartouches](https://github.com/astahfrom/cartouches), Agda's LaTeX backend,
  [Alectryon](https://github.com/cpitclaudel/alectryon).
- **Lean listings style:** [`lstlean.tex`](https://github.com/leanprover/lean4/blob/master/doc/latex/lstlean.tex).
- The need was raised on the Lean Zulip by Eric Wieser in 2022
  ([MathemaTeX](https://leanprover-community.github.io/archive/stream/113488-general/topic/MathemaTeX.html)).

## Acknowledgments

The package and its documentation were produced with the help of Claude Opus 5.5 (Anthropic)
and GPT 6.1 Sol (OpenAI), working under the authors' direction.

## License

MIT.
