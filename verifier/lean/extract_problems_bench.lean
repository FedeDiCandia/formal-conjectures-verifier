/-
Extractor for the index of the formal-conjectures archive's problems.

It is modelled on the archive's `scripts/extract_names.lean`, but adds the two
fields the verifier needs and that one does not produce:

  * `statementHasSorry` : the STATEMENT (not the proof) contains a `sorry`. This
    happens when the problem uses `answer(sorry)` with an answer that is not a
    proposition (a number, a set…). Such a statement cannot be proved honestly:
    any proof would depend on the axiom `sorryAx`.
    dall'assioma `sorryAx`.
  * `archiveProofAxioms` : which axioms the proof the archive itself supplies
    depends on. It is needed to choose the problems to exercise the agent on: 87
    of the archive's proofs use `decide +native`, which leaves the axiom
    `Lean.ofReduceBool`, and the verifier rejects them rightly. A problem
    "already solved in the archive" is therefore not necessarily solvable under
    our rules, and without this field there is no way to know in advance.
  * `range` : the theorem's position in the source file, so that the exact text of
    the statement can be cut out and the proof hidden when an agent is being
    exercised.

Usage, from the archive's directory:
    lake env lean --run <percorso>/extract_problems.lean > indice.json
-/
import Lean
import FormalConjectures.Util.Attributes.Basic

set_option linter.style.moduleDocstring false

open Lean ProblemAttributes

def categoryToString : Category → String
  | .textbook => "textbook"
  | .research .open => "research open"
  | .research .solved => "research solved"
  | .test => "test"
  | .API => "API"

def formalProofKindToString : FormalProofKind → String
  | .formalConjecturesProof => "formal_conjectures"
  | .lean4 => "lean4"
  | .otherSystem => "other_system"

def nameAny (n : Name) (p : String → Bool) : Bool :=
  match n with
  | .anonymous => false
  | .str p' s => p s || nameAny p' p
  | .num p' _ => nameAny p' p

def isInternal (n : Name) : Bool :=
  nameAny n (fun s => s.startsWith "_" || s.startsWith "match_" || s.startsWith "proof_")

partial def getAllLeanFiles (dir : System.FilePath) : IO (Array System.FilePath) := do
  let mut files := #[]
  if ← dir.isDir then
    for entry in ← dir.readDir do
      if ← entry.path.isDir then
        files := files ++ (← getAllLeanFiles entry.path)
      else if entry.path.extension == some "lean" then
        files := files.push entry.path
  return files

def getModuleNameFromFile (file : System.FilePath) : IO Name := do
  let components := file.withExtension "" |>.components
  let mut moduleComponents := []
  let mut found := false
  for c in components do
    if c == "FormalConjectures" || found then
      found := true
      moduleComponents := moduleComponents ++ [c]
  if moduleComponents.isEmpty then
    throw <| IO.userError s!"cannot determine the module of {file}"
  return moduleComponents.foldl (fun n s => Name.mkStr n s) Name.anonymous

unsafe def runWithImports {α : Type} (moduleNames : Array Name) (action : CoreM α) : IO α := do
  initSearchPath (← findSysroot)
  let imports := moduleNames.map fun n => { module := n }
  let ctx := { fileName := "", fileMap := default }
  Lean.enableInitializersExecution
  let env ← Lean.importModules imports {} (trustLevel := 1024) (loadExts := true)
  let (result, _) ← Core.CoreM.toIO action ctx { env := env }
  return result

unsafe def main : IO Unit := do
  let leanFiles ← getAllLeanFiles "FormalConjectures"
  let mut moduleNames := #[]
  for file in leanFiles do
    try moduleNames := moduleNames.push (← getModuleNameFromFile file)
    catch _ => pure ()

  runWithImports moduleNames do
    let env ← getEnv
    let tags ← getTags
    let subjectTags ← getSubjectTags
    let formalProofTags ← getFormalProofTags

    let mut categoryMap : Std.HashMap Name String := {}
    for tag in tags do
      categoryMap := categoryMap.insert tag.declName (categoryToString tag.category)

    let mut formalProofMap : Std.HashMap Name FormalProofTag := {}
    for tag in formalProofTags do
      formalProofMap := formalProofMap.insert tag.declName tag

    let mut subjectMap : Std.HashMap Name (List String) := {}
    for tag in subjectTags do
      let subjects := tag.subjects.map (fun (s : AMS) => s!"{s.toNat?.get!}")
      subjectMap := subjectMap.insert tag.declName (subjects ++ subjectMap.getD tag.declName [])

    let mut results : Array Json := #[]
    for modName in moduleNames do
      let some modIdx := env.header.moduleNames.findIdx? (· == modName) | continue
      let modData := env.header.moduleData[modIdx]!
      for info in modData.constants do
        let name := info.name
        match info with
        | ConstantInfo.thmInfo .. =>
          if isInternal name then continue
          let some category := categoryMap.get? name | continue
          let statement := toString (← Meta.MetaM.run' (Meta.ppExpr info.type))
          let docstring ← findDocString? env name
          let axioms ← collectAxioms name
          let ranges ← findDeclarationRanges? name
          let rangeJson : Json := match ranges with
            | some r => Json.mkObj [
                ("startLine", r.range.pos.line), ("startCol", r.range.pos.column),
                ("endLine", r.range.endPos.line), ("endCol", r.range.endPos.column)]
            | none => Json.null
          let (fpKind, fpLink) := match formalProofMap.get? name with
            | some tag => (Json.str (formalProofKindToString tag.proofKind), Json.str tag.proofLink)
            | none => (Json.null, Json.null)
          results := results.push <| Json.mkObj [
            ("theorem", name.toString),
            ("module", modName.toString),
            ("category", category),
            ("subjects", toJson (subjectMap.getD name [])),
            ("statement", statement),
            ("docstring", match docstring with | some d => Json.str d | none => Json.null),
            ("formalProofKind", fpKind),
            ("formalProofLink", fpLink),
            -- the PROOF is free of sorry (that is, the problem is already solved here)
            ("proofIsSorryFree", Json.bool (info.value?.any (!·.hasSorry))),
            -- the STATEMENT contains a sorry (a non-propositional answer( ) hole)
            ("statementHasSorry", Json.bool info.type.hasSorry),
            -- the axioms the archive's proof depends on
            ("archiveProofAxioms", toJson (axioms.map Name.toString)),
            ("range", rangeJson)]
        | _ => pure ()

    IO.println (Json.arr results).compress
