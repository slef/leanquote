# leanquote

Typeset Lean declarations in a LaTeX paper **by name**, copied verbatim from the Lean file that
Lean actually compiled.

```latex
\usepackage{leanquote}
\leanquotefile{Abstract.lean}
...
$P$ \emph{tiles} $\mathbb{Z}^3$ if some set $T$ of translations puts every point in exactly
one translate $t + P$:
\leanquote{Tiles}
```

The prose stays in the paper, written as usual; the code is never retyped or pasted. If a name
is misspelled, LaTeX stops with an error. If the Lean file has changed since it was exported,
LaTeX warns that the paper may show stale code.

It was written for papers that present a short, human-readable `Abstract.lean` (definitions and
main theorem statements of a formalization, proved through a bridge to the full development),
but works with any Lean 4 file.

## Usage

Put `latex/leanquote.sty` where LaTeX can find it (next to your paper, or in `TEXINPUTS`), then:

```latex
\usepackage{leanquote}
\leanquotesetup{project=../lean/}           % root of your Lake project
...
\leanquotefile{TranslationTiling/Abstract.lean} % default file for the following quotes
\leanquote{Point, Prototile}
\leanquote[doc]{Tiles}                      % with its doc comment
\leanquote[proof=false]{main_theorem}       % statement only, proof shown as := ...
\leanquote[file=Other/File.lean]{foo}       % one-off quote from another file
\leanquoteimports                           % the import block of the current file
\leanquoteimports[file=Other/File.lean]     % imports from another file
```

`\leanquotefile[options]{file}` sets the default file and options for following quotes; it works
in the preamble too. `\leanquote[options]{names}` quotes from it. The `file=...` option selects
a file for just that call, without changing the default, and works without a preceding
`\leanquotefile`. A file must be supplied by one of these methods.
`\leanquoteimports[options]` quotes the file's import block (the `module` and
`[public] import` lines at its top); it can also be named `:imports` in a list, as in
`\leanquote{:imports, Point}`. Both forms accept `file=...`.

All public commands use the `\leanquote` prefix. The former `\leanfile` alias and
`\leanfilequote{file}{names}` command were removed in v0.16; use `\leanquotefile{file}` and
`\leanquote[file=file]{names}`, respectively.

No step on the Lean side beyond your usual `lake build`:

- **Finding a declaration.** It starts at its `def`/`theorem`/`abbrev`/... line in column 0
  (with any attribute lines, and the doc comment if `doc` is set), and continues while lines are
  blank, indented, or start with `|`, `termination_by`, `decreasing_by` or `deriving`. This
  matches the standard Lean layout. Names may be short (`Tiles`) or qualified (`TranslationTiling.Abstract.Tiles`); a
  qualified name matches a declaration inside the corresponding `namespace`, since either name
  may be a dotted suffix of the other. An unknown name is an error, an ambiguous one a warning.
- **What has Lean checked?** With `project` set, quotes get a red mark in the corner of their box
  (and a warning in the log) when they are not known to be fully checked:
  - **UNVERIFIED**: the `.lean` file is newer than its compiled `.olean`, or its last `lake build`
    failed; with `verify=true`, also when there is no compiled file;
  - **USES SORRY**: the declaration depends on `sorry`, anywhere in its dependencies (needs an export);
  - **SORRY IN FILE**: Lake's build log reports a `sorry` in the file (without an export);
  - **EXTRA AXIOMS**: the declaration depends on axioms beyond `propext`, `Classical.choice`,
    `Quot.sound`, e.g. via `native_decide` (needs an export).

  By default (`verify=auto`), the code shown is thus what Lean last compiled successfully; with an
  export, it is also known not to depend on `sorry` or non-standard axioms. Without an export, a
  `sorry` in an imported file is not seen. `verify=false` turns the checks off.

All declarations named in one `\leanquote` go into one listing.

### Publishing: arXiv, CI, Overleaf

arXiv, CI builds and online editors compile the LaTeX themselves, usually without building Lean.
Include the `.lean` files and `leanquote.sty` in the upload; with the default `verify=auto`
there is no `.olean` there, so nothing is marked. Do the check where Lean is built: run
`lake build`, compile the paper locally, check that no quote is marked UNVERIFIED, then upload.

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
If `Abstract.lean` is edited after the export, LaTeX warns and falls back to reading the
`.lean` file directly, so the paper always shows the current code. An export placed next to the
`.lean` file (`Abstract.leanquote`) is also found, and an export can be given explicitly as
`\leanquote[file=Abstract.leanquote]{...}`. The exporter is a single Lean file
(`lean/LeanQuoteExport.lean`), run with `lake env lean --run`; nothing is added to your project.

## Options

Set per quote (`\leanquote[doc]{...}`), per file (`\leanquotefile[...]{...}`), or for the whole document
(`\leanquotesetup{...}`).

| Option | Default | Meaning |
|---|---|---|
| `file=<path>` | current file | select the file to quote; per-call overrides leave the default unchanged |
| `doc` | false | also show each declaration's doc comment |
| `proof` | true | with `proof=false`, theorems and lemmas stop at the `:=` of their proof, shown as `:= ...` (definitions keep their bodies) |
| `box` | true | put the listing in a light box (`leanquotebox`) |
| `logo=<file>` | none | image shown in the box's top-right corner, followed by a small TM (`\leanquotelogomark`, as the [Lean trademark policy](https://lean-lang.org/trademark-policy) requires for the Lean logo; redefine it as empty for other logos). The Lean logo is not included. Put `\leanquotetrademark` (the notice "Lean and the Lean logo are trademarks of Lean FRO.") once in the paper, e.g. in the acknowledgments. |
| `style=<name>` | `leanquote` | listings style; the default handles common Lean Unicode for pdfLaTeX |
| `project=<dir>/` | empty | root of the Lake project; `.lean` paths are relative to it |
| `olean=<file>` | | the compiled file to compare with, if not at the standard place |
| `verify=<mode>` | `auto` | `auto`: mark a quote UNVERIFIED if its `.lean` is newer than its `.olean`; `true`: also if there is no `.olean`; `false`: no check (old name: `check`) |
| `root=<dir>/`, `source=<path>` | | for exports: where to find the recorded `.lean` source |
| any other key | | passed to listings (e.g. `basicstyle=\footnotesize\ttfamily`); in `\leanquotesetup` it applies to all later quotes |

The default style colours keywords (blue), sorts and common Lean/Mathlib types such as `Nat`,
`Fin`, `Set`, `List`, `Finset`, `Real` (green), common tactics (purple) and `sorry` (red). A word right after a dot is not coloured, so `Set`
is green in `Set.univ` but import paths like `Mathlib.MeasureTheory.Measure.Lebesgue.Basic` stay
plain. Add
your own types with `\leanquotesetup{morekeywords=[2]{Prototile, Point}}` (`[3]` for tactics);
the colours are `leanquotekeyword`, `leanquotetype` and `leanquotetactic`.

## Texlish

[Texlish](https://texlish.org) passes LaTeX commands through, so `::use leanquote` works as is,
and the one-argument forms read naturally:

```
\leanquotefile: Abstract.lean
\leanquote: main_theorem
```

(With an option, use braces: `\leanquote[doc]{main_theorem}`; Texlish's colon form does not
take an optional argument.)

## Example

`example/example.tex` typesets the abstract of
[translation-tiling-paper](https://github.com/edemaine/translation-tiling-paper) from a copy of
its `Abstract.lean` (and, once, from the optional export `example/Abstract.leanquote`):

```sh
cd example && TEXINPUTS=../latex: pdflatex example.tex
```

## What is and is not guaranteed

- The code shown is the current text of the `.lean` file. With `project` set and no warning, that
  file is older than its compiled `.olean`, so it is what Lean last compiled (assuming the build
  succeeded, which is when Lake writes the `.olean`). LaTeX never compiles Lean itself.
- The default style typesets about a hundred of Lean's Unicode symbols as math, under pdfLaTeX,
  LuaLaTeX and XeLaTeX. Others can be added with `literate` (pdfLaTeX) or a monospace font that
  has them (LuaLaTeX, XeLaTeX).

Tested with pdfLaTeX, LuaLaTeX and XeLaTeX from TeX Live 2025, and with Lean v4.28.0, v4.31.0
and v4.35.0 (exporter).

## Documentation

Download the manual PDF from [GitHub releases](https://github.com/slef/leanquote/releases),
or find it at `doc/leanquote-doc.pdf` in the CTAN archive. From a Git checkout or an
extracted CTAN archive, `./make-ctan.sh` builds the manual from `doc/leanquote-doc.tex`
and writes `leanquote.zip`. It requires a POSIX shell (Cygwin on Windows), pdfLaTeX,
zip and unzip; unrelated files in `build/` are preserved.
Generated PDFs are distributed as build/release assets rather than tracked in Git.

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

The package and its documentation were produced with the help of Claude Opus 5.5 (Anthropic),
working under the authors' direction.

## License

MIT.
