/-
Run from a Lake project root:
  lake env lean --run path/to/LeanQuoteExport.lean [--no-statements] MODULE [SOURCE.lean OUTPUT.leanquote]

Lake resolves the source and compiled artifact and builds the module before export. The
optional source argument is checked against Lake, never used to override its resolution.
The default output is .lake/build/leanquote/<actual source path>.leanquote, independently
of custom Lake build directories, matching the LaTeX reader's discovery convention.

Version 3 adds declaration kinds and optional statement views to v2's provenance,
exact declaration slices, axiom dependencies, and source snapshot. Collecting views
replays the frontend in an isolated process; --no-statements skips this extra pass.
All payload lines have a prefix, so source text cannot terminate a record.
-/
import Lean
import Lean.Util.CollectAxioms
import Lean.Elab.Frontend
import Lake
import Lake.Load.Workspace
open Lean System

namespace LeanQuoteExport

-- Capture the script's path during elaboration, including for relative --run paths.
elab "leanquoteExporterFile%" : term => return toExpr (← getFileName)
private def exporterFile : String := leanquoteExporterFile%

-- The isolated collector is elaborated with the module's -D flags. Capture
-- those options here instead of approximating Lean's command-line parser.
elab "leanquoteCollectorOptions%" : term => do
  let options := LeanOptions.fromOptions? (← getOptions) |>.getD {}
  return toExpr (toJson options).compress
private def collectorOptions : String := leanquoteCollectorOptions%

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
      env := #[("LEANQUOTE_EXPORTER_FILE", some script.toString)]
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

structure StatementBoundary where
  selection : DeclarationRange
  proof : Position
  endPos : Position
  deriving Inhabited

structure SourceSyntax where
  fields : Array DeclarationRange := #[]
  statements : Array StatementBoundary := #[]

/-- Inspect parsed declaration children, never search a term for textual `:=`.
The declaration name and body positions are checked against compiled ranges later.
This also handles lemma syntax that reuses Lean's declId/declVal parsers. -/
partial def collectStatements (map : FileMap) (stx : Syntax) : Array StatementBoundary := Id.run do
  let ids := stx.getArgs.filter (·.isOfKind ``Parser.Command.declId)
  let bodies := stx.getArgs.filter fun child =>
    child.isOfKind ``Parser.Command.declValSimple ||
    child.isOfKind ``Parser.Command.declValEqns ||
    child.isOfKind ``Parser.Command.whereStructInst
  let mut result := #[]
  if ids.size == 1 && bodies.size == 1 then
    let id := ids[0]![0]
    let body := bodies[0]!
    if let (some start, some stop, some proof, some tail) :=
        (id.getPos?, id.getTailPos?, body.getPos?, body.getTailPos?) then
      result := result.push {
        selection := {pos := map.toPosition start, endPos := map.toPosition stop,
                      charUtf16 := 0, endCharUtf16 := 0}
        proof := map.toPosition proof, endPos := map.toPosition tail}
  return result ++ stx.getArgs.flatMap (collectStatements map)

def positionJson (p : Position) : Array Json := #[toJson p.line, toJson p.column]

/-- Replay the actual frontend in an isolated process. Parsing and elaboration
advance together, so namespaces, local notation, macros, and options have their
original scopes. The process writes positions only, never trusted axiom metadata. -/
unsafe def collectSourceSyntax (mod path snapshot output : String) : IO Unit := do
  initSearchPath (← findSysroot)
  enableInitializersExecution
  let source ← IO.FS.readFile snapshot
  let options : LeanOptions ← IO.ofExcept (fromJson? (← IO.ofExcept (Json.parse collectorOptions)))
  let opts := options.toOptions.setBool `Elab.async false
  let input := Parser.mkInputContext source path
  let (header, parser, messages) ← Parser.parseHeader input
  let (env, messages) ← Elab.processHeader header opts messages input (mainModule := mod.toName)
  if messages.hasErrors then
    for message in messages.toList do IO.eprintln (← message.toString)
    fail "source header replay failed"
  let (_, state) ← (Elab.Frontend.processCommands.run {inputCtx := input}).run {
    commandState := Elab.Command.mkState env messages opts,
    parserState := parser, cmdPos := parser.pos}
  if state.commandState.messages.hasErrors then
    for message in state.commandState.messages.toList do
      if message.severity == .error then IO.eprintln (← message.toString)
    fail "source syntax replay failed"
  let fields := state.commands.flatMap (collectFields input.fileMap)
  let statements := state.commands.flatMap (collectStatements input.fileMap)
  let json := Json.mkObj [
    ("fields", toJson (fields.map fun r =>
      Json.arr (positionJson r.pos ++ positionJson r.endPos))),
    ("statements", toJson (statements.map fun r =>
      Json.arr (positionJson r.selection.pos ++ positionJson r.selection.endPos ++
                positionJson r.proof ++ positionJson r.endPos)))]
  IO.FS.writeFile output json.compress

def readPosition (values : Array Json) (offset : Nat) : Except String Position := do
  return {line := ← values[offset]!.getNat?, column := ← values[offset+1]!.getNat?}

def readSourceSyntax (json : Json) : Except String SourceSyntax := do
  let fields ← (← (← json.getObjVal? "fields").getArr?).mapM fun value => do
    let a ← value.getArr?
    unless a.size == 4 do throw "invalid field positions"
    return {pos := ← readPosition a 0, endPos := ← readPosition a 2,
            charUtf16 := 0, endCharUtf16 := 0 : DeclarationRange}
  let statements ← (← (← json.getObjVal? "statements").getArr?).mapM fun value => do
    let a ← value.getArr?
    unless a.size == 8 do throw "invalid statement positions"
    return {selection := {pos := ← readPosition a 0, endPos := ← readPosition a 2,
                          charUtf16 := 0, endCharUtf16 := 0},
            proof := ← readPosition a 4, endPos := ← readPosition a 6 : StatementBoundary}
  return {fields, statements}

def sourceSyntax (target : Lake.Module) (source path : String) : IO (Option SourceSyntax) := do
  try
    IO.FS.withTempDir fun dir => do
      let script := (← IO.getEnv "LEANQUOTE_EXPORTER_FILE").getD exporterFile
      let snapshot := dir / "source.lean"
      let output := dir / "syntax.json"
      IO.FS.writeFile snapshot source
      let mut args := (target.weakLeanArgs ++ target.leanArgs).filter (·.startsWith "-D")
      for (name, value) in target.leanOptions.values do
        args := args.push s!"-D{name}={value.asCliFlagValue}"
      let child ← IO.Process.output {
        cmd := (← findSysroot) / "bin" / "lean" |>.toString
        args := args ++ #["--run", script, "--collect-syntax", target.name.toString,
                          path, snapshot.toString, output.toString]}
      unless child.exitCode == 0 do fail s!"collector exited {child.exitCode}: {child.stdout}{child.stderr}"
      return some (← IO.ofExcept (readSourceSyntax (← IO.ofExcept (Json.parse (← IO.FS.readFile output)))))
  catch e =>
    IO.eprintln s!"leanquote: statement views unavailable for {path}: {e}"
    return none

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
  isTheorem : Bool

def before (a b : Entry) : Bool :=
  a.range.pos.line < b.range.pos.line ||
  (a.range.pos.line == b.range.pos.line &&
    (a.range.pos.column < b.range.pos.column ||
      (a.range.pos.column == b.range.pos.column && a.name.toString < b.name.toString)))

def payload (tag text : String) : String :=
  if text.isEmpty then "" else
    String.join ((text.splitOn "\n").map fun line => s!"{tag} {line}\n")

/-- V2 metadata is line-oriented; axiom names additionally use whitespace as a
separator. Reject unrepresentable values before replacing an existing export. -/
def checkMetadata (label value : String) (word := false) : IO Unit := do
  if value.toList.any (fun c => c.toNat < 32 || c.toNat == 127) then
    fail s!"unsupported control character in {label}: {reprStr value}"
  if word && value.toList.any Char.isWhitespace then
    fail s!"unsupported whitespace in {label}: {reprStr value}"

def exportModule (args : List String) : IO Unit := do
  let (statements, args) := match args with
    | "--no-statements" :: rest => (false, rest)
    | "--statements" :: rest => (true, rest)
    | _ => (true, args)
  let (modStr, requested) ← match args with
    | [mod] => pure (mod, none)
    | [mod, src, out] => pure (mod, some (src, out))
    | _ => fail "usage: LeanQuoteExport [--no-statements] MODULE [SOURCE.lean OUTPUT.leanquote]"
  let mod := modStr.toName
  let root ← IO.currentDir
  let ws ← loadWorkspace
  let target ← resolveModule ws mod
  let srcPath ← relativePath root target.leanFile
  checkMetadata "module name" mod.toString
  checkMetadata "source path" srcPath
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
  checkMetadata "compiled artifact path" oleanPath
  let traceText ← IO.FS.readFile target.traceFile
  let trace ← IO.ofExcept (Json.parse traceText)
  let depHash ← IO.ofExcept (trace.getObjValAs? String "depHash")
  if depHash.isEmpty || depHash.toList.any Char.isWhitespace then fail "invalid Lake depHash"
  let source ← IO.FS.readFile target.leanFile
  unless sourceBefore == source do fail "source changed during build; retry"
  -- CRLF and LF describe the same Lean line/column positions. Emit LF payloads on
  -- every platform, while retaining the original bytes for the race checks below.
  let text := source.replace "\r\n" "\n"
  -- TeX also treats bare CR as a line ending, which could bypass LF framing.
  if text.contains '\r' then fail "unsupported bare carriage return in source; use LF or CRLF"
  let lines := (text.splitOn "\n").toArray
  let env ← importModules #[{module := mod}] {}
  let some idx := env.getModuleIdx? mod | fail s!"module {mod} not imported"
  let parsed? ← if statements then sourceSyntax target text srcPath else pure none
  -- A successful replay is authoritative, even when there are no fields.
  let parsed : SourceSyntax ← match parsed? with
    | some parsed => pure parsed
    | none => do
      let fields ← fieldRanges env text srcPath
      pure {fields}
  let ctx : Core.Context := {fileName := srcPath, fileMap := default}
  let mut entries : Array Entry := #[]
  for n in env.header.moduleData[idx.toNat]!.constNames do
    let (r?, _) ← (findDeclarationRanges? n : CoreM _).toIO ctx {env}
    let some r := r? | continue
    unless sourceFacing env n (slice lines r.selectionRange) do continue
    let range := if r.range == r.selectionRange then
        (parsed.fields.find? (contains · r.selectionRange)).getD r.range
      else r.range
    let (axs, _) ← (collectAxioms n : CoreM _).toIO ctx {env}
    entries := entries.push {
      name := privateToUserName n, range,
      selection := r.selectionRange, axioms := axs,
      isTheorem := (env.find? n).any fun ci => match ci with | .thmInfo _ => true | _ => false}
  -- A constructor named `elim`, for example, also generates `elim.elim` with the
  -- same selection. Even matching name suffixes do not make these source names.
  entries := entries.filter fun entry => !entries.any fun parent =>
    parent.name != entry.name && parent.name.isPrefixOf entry.name &&
      parent.selection == entry.selection
  let mut out := s!"@@leanquote-export 3\n@@module {mod}\n@@source {srcPath}\n@@olean {oleanPath}\n@@trace {depHash}\n"
  let mut seen : Std.HashSet Name := {}
  for entry in entries.qsort before do
    checkMetadata "declaration name" entry.name.toString
    for axiomName in entry.axioms do
      checkMetadata "axiom name" axiomName.toString (word := true)
    if seen.contains entry.name then fail s!"ambiguous source-facing name {entry.name}"
    seen := seen.insert entry.name
    let (doc, code) := splitDoc (slice lines entry.range)
    out := out ++ s!"@@begin {entry.name}\n@@axioms"
    if !entry.axioms.isEmpty then
      out := out ++ " " ++ " ".intercalate (entry.axioms.toList.map toString)
    out := out ++ s!"\n@@kind {if entry.isTheorem then "theorem" else "declaration"}\n" ++
      payload "@@doc" doc ++ payload "@@code" code
    if entry.isTheorem then
      let boundaries := parsed.statements.filter fun b =>
        b.selection.pos == entry.selection.pos && b.selection.endPos == entry.selection.endPos &&
        b.endPos == entry.range.endPos && posLE entry.selection.endPos b.proof
      if boundaries.size == 1 then
        let header := slice lines {entry.range with endPos := boundaries[0]!.proof}
        let header := String.ofList (header.toList.reverse.dropWhile (fun c => c == ' ' || c == '\t')).reverse
        let (_, statement) := splitDoc (header ++ " := ...")
        out := out ++ payload "@@statement" statement
    out := out ++ "@@end\n"
  -- Keep every source character: spaces and tabs inside multiline strings
  -- are significant. The reader normalizes CRLF and a final newline only.
  let srcLines := if lines.back? == some "" then lines.pop else lines
  for line in srcLines do
    out := out ++ s!"@@src {line}\n"
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

unsafe def main (args : List String) : IO UInt32 := do
  try
    match args with
    | ["--collect-syntax", mod, path, snapshot, output] =>
      LeanQuoteExport.collectSourceSyntax mod path snapshot output
      return 0
    | _ => return ← LeanQuoteExport.runWithNativeLake args
  catch e =>
    IO.eprintln e
    return 1
