"""Read-only Tradier market-data client. No account or order methods."""
import os
from typing import Any
import requests
class TradierConfigurationError(ValueError): pass
class TradierAPIError(RuntimeError): pass
class TradierClient:
 _BASE_URLS={"sandbox":"https://sandbox.tradier.com/v1","production":"https://api.tradier.com/v1"}
 def __init__(self,api_token=None,environment=None,session=None):
  self.api_token=api_token or os.getenv("TRADIER_API_TOKEN"); self.environment=(environment or os.getenv("TRADIER_ENVIRONMENT","sandbox")).lower()
  if self.environment not in self._BASE_URLS: raise TradierConfigurationError("TRADIER_ENVIRONMENT must be sandbox or production.")
  if not self.api_token: raise TradierConfigurationError("TRADIER_API_TOKEN is required.")
  self.base_url=self._BASE_URLS[self.environment]; self.session=session or requests.Session(); self.session.headers.update({"Authorization":"Bearer "+self.api_token,"Accept":"application/json"})
 def get_quote(self,symbol): return self._get("markets/quotes",{"symbols":symbol.upper()})
 def get_option_expirations(self,symbol): return self._get("markets/options/expirations",{"symbol":symbol.upper()})
 def get_option_chain(self,symbol,expiration): return self._get("markets/options/chains",{"symbol":symbol.upper(),"expiration":expiration})
 def _get(self,path,params):
  try:
   response=self.session.get(self.base_url+"/"+path,params=params,timeout=15); response.raise_for_status(); payload=response.json()
  except requests.RequestException as error: raise TradierAPIError("Tradier market-data request failed: "+str(error)) from error
  except ValueError as error: raise TradierAPIError("Tradier returned a non-JSON response.") from error
  if not isinstance(payload,dict): raise TradierAPIError("Tradier returned an unexpected response structure.")
  return payload
