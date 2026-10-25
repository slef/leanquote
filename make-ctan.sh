#!/bin/sh
# Build the manual and the CTAN upload archive leanquote.zip (in the repository root).
set -eu
cd "$(dirname "$0")"
version=$(sed -n 's/.*ProvidesExplPackage{leanquote}{\([^}]*\)}{\([^}]*\)}.*/\2 (\1)/p' latex/leanquote.sty)
echo "leanquote $version"
(cd doc && for i in 1 2; do
  TEXINPUTS=../latex: pdflatex -halt-on-error -interaction=nonstopmode leanquote-doc.tex >/dev/null || {
    echo "manual build failed; see doc/leanquote-doc.log" >&2
    exit 1
  }
done)
grep -q '^!' doc/leanquote-doc.log && { echo "manual has LaTeX errors"; exit 1; }
# Never use the caller's build/ directory, even for staging. Keep the previous
# archive until its replacement is complete, and remove only our private staging.
stage=$(mktemp -d "$PWD/.leanquote-ctan.XXXXXX")
trap 'rm -rf "$stage"' 0
trap 'exit 1' 1 2 3 15
package=$stage/leanquote
mkdir -p "$package/latex" "$package/doc" "$package/example/TranslationTiling" "$package/lean"
cp README.md LICENSE leanquote-export make-ctan.sh "$package/"
cp latex/leanquote.sty "$package/latex/"
cp doc/leanquote-doc.tex doc/leanquote-doc.pdf "$package/doc/"
cp example/example.tex example/Abstract.leanquote "$package/example/"
cp example/TranslationTiling/Abstract.lean "$package/example/TranslationTiling/"
cp lean/LeanQuoteExport.lean "$package/lean/"
# cp preserves restrictive source modes; umask can restrict new directories too.
# Normalize before zip records the Unix permissions, including on Cygwin.
find "$package" -type d -exec chmod 755 {} +
find "$package" -type f -exec chmod 644 {} +
chmod 755 "$package/leanquote-export" "$package/make-ctan.sh"
(cd "$stage" && zip -qr leanquote.zip leanquote)
chmod 644 "$stage/leanquote.zip"
mv -f "$stage/leanquote.zip" leanquote.zip
echo "wrote leanquote.zip:"; unzip -l leanquote.zip | tail -n +4 | sed '$d' | sed '$d'
