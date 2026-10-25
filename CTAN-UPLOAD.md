# CTAN upload (not part of the archive)

Upload page: https://ctan.org/upload. Build the archive with `./make-ctan.sh`.

| Field | Value |
|---|---|
| Name of your contribution | leanquote |
| Maintainer | Stefan Langerman; Erik D. Demaine |
| Email | (one maintainer's address) |
| Suggested CTAN directory | /macros/latex/contrib/leanquote |
| License | MIT License |
| Home page | https://github.com/slef/leanquote |
| Bug tracker | https://github.com/slef/leanquote/issues |
| Repository | https://github.com/slef/leanquote |
| Version | 0.18 2026-10-26 |
| Summary | Quote Lean 4 declarations in LaTeX by name |
| Topics | listing, verbatim, proof (formal), maths (computer-assisted) |

Description:

> leanquote typesets declarations of a Lean 4 file in a LaTeX document by name:
> `\leanquotesetup{file=Abstract.lean}` followed by `\leanquote{main_theorem}` prints the declaration exactly
> as it appears in the Lean source, read at compile time, avoiding pasted copies.
> Unknown names are errors, and the package warns when local build or export metadata is stale.
> An optional exporter uses Lean's exact declaration boundaries and checks axiom dependencies.
> Works with pdfLaTeX, LuaLaTeX and XeLaTeX.

Before uploading:
- [x] make the GitHub repository public;
- [x] prior-art check done (`PRIOR-ART.md`); related tools credited in the manual and README;
- [ ] decide the license (MIT now; LPPL 1.3c is the CTAN default);
- [ ] read the manual once more;
- [ ] Lean FRO's answer on bundling the logo (email drafted 2026-10-25).
