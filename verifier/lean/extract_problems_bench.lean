/-
Estrattore dell'indice dei problemi dell'archivio formal-conjectures.

E' modellato su `scripts/extract_names.lean` dell'archivio, ma aggiunge i due
campi che servono al verificatore e che quello non produce:

  * `statementHasSorry` : l'ENUNCIATO (non la dimostrazione) contiene un
    `sorry`. Succede quando il problema usa `answer(sorry)` con una risposta
    che non e' una proposizione (un numero, un insieme...). Un enunciato del
    genere non e' dimostrabile onestamente: qualunque prova dipenderebbe
    dall'assioma `sorryAx`.
  * `archiveProofAxioms` : da quali assiomi dipende la dimostrazione che
    l'archivio stesso fornisce. Serve per scegliere i problemi di collaudo: 87
    dimostrazioni dell'archivio usano `decide +native`, che lascia l'assioma
    `Lean.ofReduceBool`, e il verificatore le rifiuta a ragione. Un problema
    "gia' risolto nell'archivio" non e' quindi detto sia risolvibile sotto le
    nostre regole, e senza questo campo non c'e' modo di saperlo in anticipo.
  * `range` : la posizione del teorema nel file sorgente, per poter ritagliare
    il testo esatto dell'enunciato e per nascondere la dimostrazione quando si
    collauda un agente.

Uso, dalla cartella dell'archivio:
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
    throw <| IO.userError s!"Impossibile determinare il modulo di {file}"
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
          let assiomi ← collectAxioms name
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
            -- la DIMOSTRAZIONE e' priva di sorry (cioe' il problema e' gia' risolto qui)
            ("proofIsSorryFree", Json.bool (info.value?.any (!·.hasSorry))),
            -- l'ENUNCIATO contiene un sorry (buco answer( ) non proposizionale)
            ("statementHasSorry", Json.bool info.type.hasSorry),
            -- gli assiomi da cui dipende la dimostrazione dell'archivio
            ("archiveProofAxioms", toJson (assiomi.map Name.toString)),
            ("range", rangeJson)]
        | _ => pure ()

    IO.println (Json.arr results).compress
