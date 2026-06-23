from dataclasses import dataclass
from typing import Mapping
@dataclass(frozen=True,slots=True)
class IndicatorSnapshot:
 symbol:str; observed_at:str; values:Mapping[str,float]
