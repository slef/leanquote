# Prior art for leanquote (checked 2026-10-25)

Conclusion: nothing found quotes a Lean declaration by name, verbatim from the `.lean` file, at
LaTeX compile time, with a check against the compiled `.olean`. The pieces exist separately.

## Generic LaTeX inclusion by marker, tag or regex (all need markers or regexes in practice)

| Tool | Notes |
|---|---|
| catchfilebetweentags (CTAN) | `\ExecuteMetaData[file]{tag}` between `%<*tag>` / `%</tag>` markers; the classic, used by Agda. |
| listings `linerange` with `rangeprefix`/`rangesuffix` | Marker comments instead of line numbers. |
| minted 3 `rangeregex`, `rangestartstring`… (CTAN, active) | Closest general tool; Pygments has a `lean4` lexer. No unknown-name errors, no doc/namespace handling, no staleness check; needs Python. |
| piton `\PitonInputFile[range=…]` (CTAN, LuaLaTeX) | Marker ranges; no Lean language. |
| tagsnip (CTAN, July 2026, MIT) | `\IncludeCode{source}{tag}…` between `tagsnip-start/end` markers; Python + minted + shell escape. Current generic alternative. |
| Sphinx `literalinclude :pyobject:`, mdBook anchors | By-name precedent outside TeX (Python). |

## Proof assistants and Lean

| Tool | Notes |
|---|---|
| Verso `Verso.Code.External` + SubVerso (Lean FRO) | Same goal in a Lean-native document: anchors `-- ANCHOR: X`, highlighted, mismatch is an error; TeX output via VersoManual. Different paradigm (document written in Verso). Credit. |
| SubVerso `subverso-extract-mod` | Per-command defined names + highlighted code (JSON); possible future backend. |
| leanblueprint `\lean{}`, `checkdecls` | Links names to doc-gen, checks existence; does not typeset code. Complementary. |
| LeanArchitect (`\inputleannode{name}`) | Lean name → LaTeX input, but transports LaTeX prose, not code. |
| Isabelle snippets (`sugar.pdf` §7); isasnips → cartouches | Cartouches names snippets automatically from declarations: closest by-name precedent (Isabelle, separate build step). |
| Agda `--latex` + catchfilebetweentags | By marker; type-checked at generation. |
| Alectryon, LeanInk (archived 2024) | Annotated code with goals; snippets by marker. |
| `lstlean.tex` (official Lean docs) | listings language `lean` with a Unicode `literate` table; no file inclusion. |
| LeanTeX, `run_latex`, lean2tex, RepLeanTeX, span | Pretty-printing, kernel-type rewriting, REPL calls, label ledgers: partial overlap, not verbatim quoting. |
| Lean Zulip "MathemaTeX" (Dec 2022) | Eric Wieser proposed `\includeleansnippet{file}{ids}` against drift; never implemented. Motivation to cite. |

No LaTeX package compares quoted source with a build artifact; Verso, Isabelle, Agda and
Alectryon get freshness because the checker generates the document.

## Naming

- CTAN: no `leanquote`, `leanfile`, `lean`, `lean4`; no package mentions Lean. TeX Live 2025 has
  none of our command or environment names.
- Clash: several blueprint preambles define `\leanfile` themselves (physicslib4, YoungDiagram,
  PrimeTensor-NS, mathematical-physics-lean; `\newwrite\leanfile` in chiral-gauge-dynamics).
- Clash: many papers define `\lstdefinelanguage{Lean4}`; listings lowercases names, so it would
  silently replace our `lean4` language and its Unicode table.
- Unrelated: `jpcg199810/-leanquote-mvp` is a web app, not TeX.

## Suggestions from the check

- Use expl3 `\file_compare_timestamp:nNnTF` instead of slicing `\pdf@filemoddate` (timezone).
- "Did you mean …" suggestions for unknown names (as Verso does).
- Optional minted/Pygments `lean4` output for Unicode engines.
- Credit the tools above in the manual.

Full report with sources: in the Claude session of 2026-10-25 (abstractlean repo context).
