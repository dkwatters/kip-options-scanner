from dataclasses import dataclass,field
from typing import Mapping
@dataclass(frozen=True,slots=True)
class ScoreComponent:
 name:str; value:float; weight:float; rationale:str=""
@dataclass(frozen=True,slots=True)
class ScoreResult:
 total:float; components:tuple[ScoreComponent,...]=(); metadata:Mapping[str,str]=field(default_factory=dict)
