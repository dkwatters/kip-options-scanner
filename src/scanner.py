from dataclasses import dataclass,field
from datetime import datetime
from typing import Mapping,Sequence
from src.scoring import ScoreResult
from src.universe import UniverseSymbol
class ScannerNotImplementedError(NotImplementedError): pass
@dataclass(frozen=True,slots=True)
class ScanResult:
 symbol:str; score:ScoreResult; summary:str=""; metadata:Mapping[str,str]=field(default_factory=dict)
@dataclass(frozen=True,slots=True)
class ScanRun:
 started_at:datetime; universe_size:int; results:tuple[ScanResult,...]=()
def run_scan(universe:Sequence[UniverseSymbol])->ScanRun:
 raise ScannerNotImplementedError("Scanning is not implemented in Phase 1A. This release only provides the project scaffold.")
