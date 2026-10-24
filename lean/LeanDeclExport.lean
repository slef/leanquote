/-
leandecl exporter: writes the exact source text of every declaration of a compiled Lean module
to a `.leandecl` file, for the `leandecl` LaTeX package.

Usage, from the root of a Lake project in which `MODULE` has been built:

  lake env lean --run path/to/LeanDeclExport.lean MODULE SOURCE.lean OUTPUT.leandecl

The declaration ranges come from the compiled module (`.olean`), so they describe the version
of `SOURCE.lean` that Lean last compiled. Run `lake build MODULE` first (the `leandecl-export`
shell script does both). The file also records the source text, so that the LaTeX package can
warn when `SOURCE.lean` has changed since the export.
-/
import Lean
open Lean

/-- Declarations a reader would cite: skip internal and auxiliary names. -/
def citable (env : Environment) (n : Name) : Bool :=
  !n.isInternal && !isAuxRecursor env n && !isNoConfusion env n && !n.isImplementationDetail

def main (args : List String) : IO UInt32 := do
  let [modStr, srcPath, outPath] := args
    | IO.eprintln "usage: LeanDeclExport MODULE SOURCE.lean OUTPUT.leandecl"; return 1
  let mod := modStr.toName
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module := mod }] {}
  let some idx := env.getModuleIdx? mod
    | IO.eprintln s!"leandecl: module {mod} not found"; return 1
  let lines := (← IO.FS.readFile srcPath).splitOn "\n" |>.toArray
  let ctx : Core.Context := { fileName := srcPath, fileMap := default }
  let mut entries : Array (Nat × Name × Nat × Nat × Bool) := #[]
  for n in env.header.moduleData[idx.toNat]!.constNames do
    unless citable env n do continue
    let (r?, _) ← (findDeclarationRanges? n : CoreM _).toIO ctx { env }
    let some r := r? | continue
    -- `range` covers the whole command, including any doc comment.
    let hasDoc := (← findDocString? env n).isSome
    entries := entries.push (r.range.pos.line, n, r.range.pos.line, r.range.endPos.line, hasDoc)
  let sorted := entries.qsort (fun a b => a.1 < b.1)
  let mut out := s!"@@leandecl-export 1\n@@module {mod}\n@@source {srcPath}\n"
  let mut seen : Std.HashSet Nat := {}
  for (_, n, first, last, hasDoc) in sorted do
    if seen.contains first then continue  -- e.g. structure fields share their parent's range
    seen := seen.insert first
    let text := (lines.extract (first - 1) last).toList
    -- Separate the doc comment (if any) from the code.
    let (doc, code) :=
      if hasDoc then
        let i := (text.findIdx? fun l => (String.mk (l.toList.reverse.dropWhile Char.isWhitespace).reverse).endsWith "-/").getD 0
        (text.take (i + 1), text.drop (i + 1))
      else ([], text)
    out := out ++ s!"@@begin {n}\n"
    for l in doc do out := out ++ s!"@@doc {l}\n"
    for l in code do out := out ++ l ++ "\n"
    out := out ++ "@@end\n"
  -- The source as compiled, so that LaTeX can warn when the file has changed since.
  -- (Trailing whitespace and a final empty line are dropped, as TeX does when reading a file.)
  let srcLines := if lines.back? == some "" then lines.pop else lines
  for l in srcLines do
    out := out ++ s!"@@src {String.mk (l.toList.reverse.dropWhile Char.isWhitespace).reverse}\n"
  IO.FS.writeFile outPath out
  IO.println s!"leandecl: wrote {seen.size} declarations of {mod} to {outPath}"
  return 0
