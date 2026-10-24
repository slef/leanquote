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

## Two parts

1. **`leandecl-export`** (Lean side). From the root of the Lake project:

   ```sh
   path/to/leandecl/leandecl-export TranslationTiling.Abstract ../paper/Abstract.leandecl
   ```

   This runs `lake build` on the module, then writes every declaration of the compiled module to
   a `.leandecl` file: its exact text (from Lean's own declaration ranges), its doc comment kept
   separately, and a copy of the source as compiled. No dependency to add to your project; the
   exporter is a single Lean file (`lean/LeanDeclExport.lean`) run with `lake env lean --run`.

2. **`leandecl.sty`** (LaTeX side). Put `latex/leandecl.sty` where LaTeX can find it (next to
   your paper, or in `TEXINPUTS`), then:

   ```latex
   \leandecl[options]{file}{Name1, Name2, ...}
   ```

   - `file` is a `.leandecl` export (recommended) or a `.lean` file. Reading a `.lean` file
     directly also works, but a declaration is then taken to run from its `def`/`theorem`/...
     line to the next blank line.
   - Names may be short (`Tiles`) or fully qualified (`TranslationTiling.Abstract.Tiles`).
     All the named declarations are typeset together in one listing.

## Options

Set per call (`\leandecl[doc]{...}{...}`) or for the whole document (`\leandeclsetup{...}`).

| Option | Default | Meaning |
|---|---|---|
| `doc` | false | also show each declaration's doc comment |
| `box` | true | put the listing in a light box (`leandeclbox`) |
| `logo=<file>` | none | image shown in the box's top-right corner (e.g. the Lean logo) |
| `style=<name>` | `leandecl` | listings style; the default handles common Lean Unicode for pdfLaTeX |
| `check` | true | warn if the `.lean` source has changed since the export |
| `root=<dir>/` | empty | prefix for finding the `.lean` source recorded in the export, for the check |
| `source=<path>` | | the `.lean` file to check against, if it is not at the recorded path |
| any other key | | passed to `\lstinputlisting` (e.g. `basicstyle=\footnotesize\ttfamily`) |

## Texlish

[Texlish](https://texlish.org) passes LaTeX commands through, so `::use leandecl` and
`\leandecl{...}{...}` work as is.

## Example

`example/example.tex` typesets the abstract of
[translation-tiling-paper](https://github.com/edemaine/translation-tiling-paper) from
`example/Abstract.leandecl`:

```sh
cd example && TEXINPUTS=../latex: pdflatex example.tex
```

## What is and is not guaranteed

- The code shown is the text of declarations of a module that Lean compiled (when using an
  export), so it is exactly what Lean checked at export time.
- The freshness check compares the source recorded in the export with the current `.lean` file;
  it does not recompile anything. Re-run `leandecl-export` after changing the Lean file.
- The default style maps common Unicode symbols for pdfLaTeX. Other symbols can be added with
  `literate`, or use LuaLaTeX/XeLaTeX with a Unicode monospace font.

Tested with Lean v4.28.0, v4.31.0 and v4.35.0, and pdfLaTeX from TeX Live 2025.

## License

MIT. The Lean logo in `example/` belongs to the Lean FRO.
