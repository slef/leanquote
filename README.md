# leandecl

Typeset Lean declarations in a LaTeX paper **by name**, copied verbatim from the Lean file that
Lean actually compiled.

```latex
\usepackage{leandecl}
...
$P$ \emph{tiles} $\mathbb{Z}^3$ if some set $T$ of translations puts every point in exactly
one translate $t + P$:
\leandecl{Abstract.leandecl}{Tiles}
```

The prose stays in the paper, written as usual; the code is never retyped or pasted. If a name
is misspelled, LaTeX stops with an error. If the Lean file has changed since it was exported,
LaTeX warns that the paper may show stale code.

It was written for papers that present a short, human-readable `Abstract.lean` (definitions and
main theorem statements of a formalization, proved through a bridge to the full development),
but works with any Lean 4 file.

## Usage

Put `latex/leandecl.sty` where LaTeX can find it (next to your paper, or in `TEXINPUTS`), then:

```latex
\usepackage{leandecl}
\leandeclsetup{project=../lean/}   % root of your Lake project
...
\leandecl{TranslationTiling/Abstract.lean}{Point, Prototile}
\leandecl[doc]{TranslationTiling/Abstract.lean}{Tiles}
```

No step on the Lean side beyond your usual `lake build`:

- **Finding a declaration.** It starts at its `def`/`theorem`/`abbrev`/... line in column 0
  (with any attribute lines, and the doc comment if `doc` is set), and continues while lines are
  blank, indented, or start with `|`, `termination_by`, `decreasing_by` or `deriving`. This
  matches the standard Lean layout. Names may be short (`Tiles`) or qualified (`Abstract.Tiles`).
  An unknown name is an error.
- **Checking it was compiled.** If the `.lean` file is newer than its compiled
  `.lake/build/lib/lean/.../File.olean` (found from `project`), LaTeX warns that the code shown
  may not be what Lean checked. After a successful `lake build`, the `.olean` is newer, so no
  warning. If there is no `.olean` (for example, a copy of the file outside its project), LaTeX
  only notes that it cannot check.

All declarations named in one `\leandecl` go into one listing.

### Optional: exact boundaries with `leandecl-export`

For files laid out unusually, `leandecl-export MODULE out.leandecl` (run from the Lake project)
builds the module and records each declaration's exact text from Lean's own declaration
ranges, with a copy of the source; `\leandecl{out.leandecl}{Name}` then uses that, and warns if
the source has changed since the export. The exporter is a single Lean file
(`lean/LeanDeclExport.lean`), run with `lake env lean --run`.

## Options

Set per call (`\leandecl[doc]{...}{...}`) or for the whole document (`\leandeclsetup{...}`).

| Option | Default | Meaning |
|---|---|---|
| `doc` | false | also show each declaration's doc comment |
| `box` | true | put the listing in a light box (`leandeclbox`) |
| `logo=<file>` | none | image shown in the box's top-right corner (e.g. the Lean logo) |
| `style=<name>` | `leandecl` | listings style; the default handles common Lean Unicode for pdfLaTeX |
| `project=<dir>/` | empty | root of the Lake project; `.lean` paths are relative to it |
| `olean=<file>` | | the compiled file to compare with, if not at the standard place |
| `check` | true | warn if the `.lean` file is newer than its `.olean` (or, for exports, has changed since the export) |
| `root=<dir>/`, `source=<path>` | | for exports: where to find the recorded `.lean` source |
| any other key | | passed to `\lstinputlisting` (e.g. `basicstyle=\footnotesize\ttfamily`) |

## Texlish

[Texlish](https://texlish.org) passes LaTeX commands through, so `::use leandecl` and
`\leandecl{...}{...}` work as is.

## Example

`example/example.tex` typesets the abstract of
[translation-tiling-paper](https://github.com/edemaine/translation-tiling-paper) from a copy of
its `Abstract.lean` (and, once, from the optional export `example/Abstract.leandecl`):

```sh
cd example && TEXINPUTS=../latex: pdflatex example.tex
```

## What is and is not guaranteed

- The code shown is the current text of the `.lean` file. With `project` set and no warning, that
  file is older than its compiled `.olean`, so it is what Lean last compiled (assuming the build
  succeeded, which is when Lake writes the `.olean`). LaTeX never compiles Lean itself.
- The default style maps common Unicode symbols for pdfLaTeX. Other symbols can be added with
  `literate`, or use LuaLaTeX/XeLaTeX with a Unicode monospace font.

Tested with Lean v4.28.0, v4.31.0 and v4.35.0, and pdfLaTeX from TeX Live 2025.

## License

MIT. The Lean logo in `example/` belongs to the Lean FRO.
