import csv
from dataclasses import dataclass
from pathlib import Path
class UniverseError(ValueError): pass
@dataclass(frozen=True,slots=True)
class UniverseSymbol:
 symbol:str; name:str=""; sector:str=""
 def to_display_dict(self): return {"Symbol":self.symbol,"Name":self.name,"Sector":self.sector}
def load_universe(csv_path):
 path=Path(csv_path).expanduser()
 if not path.is_file(): raise UniverseError("File not found: " + str(path))
 try:
  with path.open("r",newline="",encoding="utf-8-sig") as source:
   reader=csv.DictReader(source)
   if not reader.fieldnames or "symbol" not in reader.fieldnames: raise UniverseError("CSV must include a symbol column.")
   items=[]; seen=set()
   for number,row in enumerate(reader,2):
    symbol=(row.get("symbol") or "").strip().upper(); enabled=(row.get("enabled") or "true").strip().lower()
    if not symbol: raise UniverseError("Row {}: symbol cannot be blank.".format(number))
    if enabled not in {"true","false","1","0","yes","no"}: raise UniverseError("Row {}: enabled must be true or false.".format(number))
    if enabled in {"false","0","no"}: continue
    if symbol in seen: raise UniverseError("Row {}: duplicate enabled symbol {}.".format(number,symbol))
    seen.add(symbol); items.append(UniverseSymbol(symbol,(row.get("name") or "").strip(),(row.get("sector") or "").strip()))
   return items
 except OSError as error: raise UniverseError("Could not read CSV: " + str(error)) from error
