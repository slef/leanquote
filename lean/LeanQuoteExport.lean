/-
Run from a Lake project root:
  lake env lean --run path/to/LeanQuoteExport.lean MODULE [SOURCE.lean OUTPUT.leanquote]

Lake resolves the source and compiled artifact and builds the module before export. The
optional source argument is checked against Lake, never used to override its resolution.
The default output is .lake/build/leanquote/<actual source path>.leanquote, independently
of custom Lake build directories, matching the LaTeX reader's discovery convention.

Version 2 records project-relative source/olean paths, Lake's trace depHash, exact
declaration slices, compiled axiom dependencies, and the source snapshot. All payload
lines have a prefix, including code lines, so source text cannot terminate a record.
-/
import Lean
import Lean.Util.CollectAxioms
import Lake
import Lake.Load.Workspace
open Lean System

namespace LeanQuoteExport

-- Capture the script's path during elaboration, including for relative --run paths.
elab "leanquoteExporterFile%" : term => return toExpr (← getFileName)
private def exporterFile : String := leanquoteExporterFile%

def fail {α : Type} (message : String) : IO α :=
  throw <| IO.userError s!"leanquote-export: {message}"

/-- Lake's Lean configuration loader needs native Lake support. Run this file as a
Lake script, inside Lake's already initialized native runtime. Loading Lake's plugin
into a plain Lean interpreter also has initialization problems on older toolchains.
This bootstrap preserves the documented --run interface on all supported versions. -/
def runWithNativeLake (args : List String) : IO UInt32 := do
  let (_, some _, some lake) ← Lake.findInstall?
    | fail "cannot locate Lean/Lake installation"
  let script ← IO.FS.realPath exporterFile
  let source ← IO.FS.readFile script
  -- Keep the driver ephemeral, isolated between concurrent invocations, and in this
  -- single distributable file. Plain `lean --run` cannot elaborate Lake's DSL on
  -- older versions either, so only native Lake sees the appended package/script.
  IO.FS.withTempDir fun dir => do
    let driver := dir / "LeanQuoteExportDriver.lean"
    IO.FS.writeFile driver (source ++
      "\nopen Lake DSL\npackage leanquote_exporter\n" ++
      "script leanquoteExport (args) do\n" ++
      "  try\n    LeanQuoteExport.exportModule args\n    return (0 : UInt32)\n" ++
      "  catch e =>\n    IO.eprintln e\n    return (1 : UInt32)\n")
    let child ← IO.Process.spawn {
      cmd := lake.lake.toString
      args := #["-f", driver.toString, "script", "run", "leanquoteExport"] ++ args.toArray
    }
    return ← child.wait

def loadWorkspace : IO Lake.Workspace := do
  let (elan?, some lean, some lake) ← Lake.findInstall?
    | fail "cannot locate Lean/Lake installation"
  let lakeEnv ← (Lake.Env.compute lake lean elan?).toIO IO.userError
  let config : Lake.LoadConfig := {
    lakeEnv, wsDir := (← IO.currentDir), updateToolchain := false }
  let some ws ← (Lake.loadWorkspace config).toBaseIO
    | fail "cannot load Lake workspace"
  return ws

/-- Normalize real paths before comparing, including symlinks and Windows separators. -/
def sameFile (a b : FilePath) : IO Bool := do
  return (← IO.FS.realPath a).normalize == (← IO.FS.realPath b).normalize

def relativePath (root path : FilePath) : IO String := do
  let root ← IO.FS.realPath root
  let path ← IO.FS.realPath path
  let rel := Lake.relPathFrom root path
  if rel.isAbsolute || rel.components.contains ".." then
    fail s!"path outside project root: {path}"
  return rel.toString.replace "\\" "/"

/-- Reject competing Lake libraries rather than relying on their lookup order. -/
def resolveModule (ws : Lake.Workspace) (name : Name) : IO Lake.Module := do
  let candidates := ws.packages.flatMap fun pkg =>
    pkg.leanLibs.filterMap (·.findModule? name)
  let some first := candidates[0]? | fail s!"no Lake library provides module {name}"
  for candidate in candidates do
    unless (← sameFile first.leanFile candidate.leanFile) &&
        first.oleanFile.normalize == candidate.oleanFile.normalize do
      fail s!"ambiguous Lake module {name}: {first.leanFile} and {candidate.leanFile}"
  return first

/-- Character columns are Unicode code points, not byte or UTF-16 offsets. -/
def slice (lines : Array String) (r : DeclarationRange) : String := Id.run do
  let mut parts := #[]
  for i in [r.pos.line - 1:r.endPos.line] do
    let chars := lines[i]!.toList
    let chars := if i + 1 == r.endPos.line then chars.take r.endPos.column else chars
    let chars := if i + 1 == r.pos.line then chars.drop r.pos.column else chars
    parts := parts.push (String.ofList chars)
  return "\n".intercalate parts.toList

/-- Lean stores only the name-token range for some structure projections/constructors.
Recover their syntax from parser positions, including a local doc comment. Parsing
is supplemental: custom/local syntax that cannot be replayed keeps its compiled range. -/
partial def collectFields (map : FileMap) (stx : Syntax) : Array DeclarationRange := Id.run do
  let kind := stx.getKind
  if kind == ``Parser.Command.structSimpleBinder ||
      kind == ``Parser.Command.structExplicitBinder ||
      kind == ``Parser.Command.structImplicitBinder ||
      kind == ``Parser.Command.structInstBinder ||
      kind == ``Parser.Command.structCtor then
    if let (some start, some stop) := (stx.getPos?, stx.getTailPos?) then
      return #[{
        pos := map.toPosition start, endPos := map.toPosition stop,
        charUtf16 := 0, endCharUtf16 := 0}]
  return stx.getArgs.flatMap (collectFields map)

def fieldRanges (env : Environment) (source path : String) : IO (Array DeclarationRange) := do
  let input := Parser.mkInputContext source path
  let (_, initial, _) ← Parser.parseHeader input
  let mut state := initial
  let mut ranges := #[]
  repeat
    let (stx, next, messages) := Parser.parseCommand input {env, options := {}} state {}
    unless messages.hasErrors do ranges := ranges ++ collectFields input.fileMap stx
    if Parser.isTerminalCommand stx || next.pos == state.pos then break
    state := next
  return ranges

def posLE (a b : Position) : Bool :=
  a.line < b.line || (a.line == b.line && a.column <= b.column)

def contains (outer inner : DeclarationRange) : Bool :=
  posLE outer.pos inner.pos && posLE inner.endPos outer.endPos

/-- Find a leading doc comment's lexical end, honoring nested block comments. -/
def splitDoc (text : String) : String × String := Id.run do
  let chars := text.toList.toArray
  unless text.startsWith "/--" do return ("", text)
  let mut depth := 1
  let mut i := 3
  while i + 1 < chars.size do
    if chars[i]! == '/' && chars[i + 1]! == '-' then
      depth := depth + 1
      i := i + 2
    else if chars[i]! == '-' && chars[i + 1]! == '/' then
      depth := depth - 1
      i := i + 2
      if depth == 0 then
        -- Drop only the separating newline, preserving inline code and its spaces.
        let rest := chars.toList.drop i
        let rest := if rest.head? == some '\n' then rest.drop 1 else rest
        return (String.ofList (chars.toList.take i), String.ofList rest)
    else
      i := i + 1
  return ("", text)

/-- A generated recursor/helper borrows its parent's selection range; it has no own name
in the source. Private declarations do have source names, after removing Lean's prefix. -/
def sourceFacing (env : Environment) (n : Name) (selected : String) : Bool :=
  -- Parse the source token to its canonical components: optional escaping
  -- must not drop real declarations or split dots inside an escaped name.
  match Parser.runParserCategory env `term selected with
  | .ok stx => stx.isIdent && stx.getId.isSuffixOf (privateToUserName n)
  | .error _ => false

structure Entry where
  name : Name
  range : DeclarationRange
  selection : DeclarationRange
  axioms : Array Name

def before (a b : Entry) : Bool :=
  a.range.pos.line < b.range.pos.line ||
  (a.range.pos.line == b.range.pos.line &&
    (a.range.pos.column < b.range.pos.column ||
      (a.range.pos.column == b.range.pos.column && a.name.toString < b.name.toString)))

def payload (tag text : String) : String :=
  if text.isEmpty then "" else
    String.join ((text.splitOn "\n").map fun line => s!"{tag} {line}\n")

def exportModule (args : List String) : IO Unit := do
  let (modStr, requested) ← match args with
    | [mod] => pure (mod, none)
    | [mod, src, out] => pure (mod, some (src, out))
    | _ => fail "usage: LeanQuoteExport MODULE [SOURCE.lean OUTPUT.leanquote]"
  let mod := modStr.toName
  let root ← IO.currentDir
  let ws ← loadWorkspace
  let target ← resolveModule ws mod
  let srcPath ← relativePath root target.leanFile
  if let some (src, _) := requested then
    unless ← sameFile src target.leanFile do
      fail s!"source mismatch: Lake resolves {mod} to {srcPath}, not {src}"
  let sourceBefore ← IO.FS.readFile target.leanFile
  -- Rehash inputs rather than trusting timestamp-based cached source hashes. This is
  -- also required for direct CLI callers: ranges/axioms must describe this source.
  let build ← IO.Process.output {cmd := "lake", args := #["-H", "build", modStr]}
  if !build.stdout.isEmpty then IO.print build.stdout
  if !build.stderr.isEmpty then IO.eprint build.stderr
  unless build.exitCode == 0 do fail s!"lake build {mod} failed"
  initSearchPath (← findSysroot)
  -- Loading a workspace resets Lean's search path. Use Lake's actual import order,
  -- and verify the artifact Lean will import before reading any declarations.
  searchPathRef.set ws.augmentedLeanPath
  let imported ← findOLean mod
  unless ← sameFile imported target.oleanFile do
    fail s!"compiled module mismatch: Lean imports {imported}, Lake builds {target.oleanFile}"
  let oleanPath ← relativePath root imported
  let traceText ← IO.FS.readFile target.traceFile
  let trace ← IO.ofExcept (Json.parse traceText)
  let depHash ← IO.ofExcept (trace.getObjValAs? String "depHash")
  if depHash.isEmpty || depHash.toList.any Char.isWhitespace then fail "invalid Lake depHash"
  let source ← IO.FS.readFile target.leanFile
  unless sourceBefore == source do fail "source changed during build; retry"
  -- CRLF and LF describe the same Lean line/column positions. Emit LF payloads on
  -- every platform, while retaining the original bytes for the race checks below.
  let text := source.replace "\r\n" "\n"
  let lines := (text.splitOn "\n").toArray
  let env ← importModules #[{module := mod}] {}
  let some idx := env.getModuleIdx? mod | fail s!"module {mod} not imported"
  let fields ← fieldRanges env text srcPath
  let ctx : Core.Context := {fileName := srcPath, fileMap := default}
  let mut entries : Array Entry := #[]
  for n in env.header.moduleData[idx.toNat]!.constNames do
    let (r?, _) ← (findDeclarationRanges? n : CoreM _).toIO ctx {env}
    let some r := r? | continue
    unless sourceFacing env n (slice lines r.selectionRange) do continue
    let range := if r.range == r.selectionRange then
        (fields.find? (contains · r.selectionRange)).getD r.range
      else r.range
    let (axs, _) ← (collectAxioms n : CoreM _).toIO ctx {env}
    entries := entries.push {
      name := privateToUserName n, range,
      selection := r.selectionRange, axioms := axs}
  -- A constructor named `elim`, for example, also generates `elim.elim` with the
  -- same selection. Even matching name suffixes do not make these source names.
  entries := entries.filter fun entry => !entries.any fun parent =>
    parent.name != entry.name && parent.name.isPrefixOf entry.name &&
      parent.selection == entry.selection
  let mut out := s!"@@leanquote-export 2\n@@module {mod}\n@@source {srcPath}\n@@olean {oleanPath}\n@@trace {depHash}\n"
  let mut seen : Std.HashSet Name := {}
  for entry in entries.qsort before do
    if seen.contains entry.name then fail s!"ambiguous source-facing name {entry.name}"
    seen := seen.insert entry.name
    let (doc, code) := splitDoc (slice lines entry.range)
    out := out ++ s!"@@begin {entry.name}\n@@axioms"
    if !entry.axioms.isEmpty then
      out := out ++ " " ++ " ".intercalate (entry.axioms.toList.map toString)
    out := out ++ "\n" ++ payload "@@doc" doc ++ payload "@@code" code ++ "@@end\n"
  -- TeX ignores trailing whitespace and the final newline; preserve line sequences.
  let srcLines := if lines.back? == some "" then lines.pop else lines
  for line in srcLines do
    out := out ++ s!"@@src {String.ofList (line.toList.reverse.dropWhile Char.isWhitespace).reverse}\n"
  unless source == (← IO.FS.readFile target.leanFile) &&
      traceText == (← IO.FS.readFile target.traceFile) do
    fail "source or build trace changed during export; retry"
  let outPath : FilePath := match requested with
    | some (_, out) => out
    | none => ".lake" / "build" / "leanquote" / (FilePath.mk srcPath).withExtension "leanquote"
  if let some parent := outPath.parent then IO.FS.createDirAll parent
  IO.FS.writeFile outPath out
  IO.println s!"leanquote: wrote {seen.size} declarations of {mod} to {outPath}"

end LeanQuoteExport

def main (args : List String) : IO UInt32 := do
  try
    return ← LeanQuoteExport.runWithNativeLake args
  catch e =>
    IO.eprintln e
    return 1
