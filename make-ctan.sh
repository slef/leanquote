#!/bin/sh
# Build the manual and the CTAN upload archive leanquote.zip (in the repository root).
set -eu
cd "$(dirname "$0")"
version=$(sed -n 's/.*ProvidesExplPackage{leanquote}{\([^}]*\)}{\([^}]*\)}.*/\2 (\1)/p' latex/leanquote.sty)
echo "leanquote $version"
(cd doc && for i in 1 2; do TEXINPUTS=../latex: pdflatex -interaction=nonstopmode leanquote-doc.tex >/dev/null; done)
grep -q '^!' doc/leanquote-doc.log && { echo "manual has LaTeX errors"; exit 1; }
rm -rf build/leanquote leanquote.zip
mkdir -p build/leanquote/latex build/leanquote/doc build/leanquote/example/TranslationTiling build/leanquote/lean
cp README.md LICENSE leanquote-export build/leanquote/
cp latex/leanquote.sty build/leanquote/latex/
cp doc/leanquote-doc.tex doc/leanquote-doc.pdf build/leanquote/doc/
cp example/example.tex example/Abstract.leanquote build/leanquote/example/
cp example/TranslationTiling/Abstract.lean build/leanquote/example/TranslationTiling/
cp lean/LeanQuoteExport.lean build/leanquote/lean/
(cd build && zip -qr ../leanquote.zip leanquote)
rm -rf build
echo "wrote leanquote.zip:"; unzip -l leanquote.zip | tail -n +4 | sed '$d' | sed '$d'
