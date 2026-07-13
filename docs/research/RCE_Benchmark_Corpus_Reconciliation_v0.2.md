# RCE Benchmark Corpus Reconciliation v0.2

The corpus contains exactly **17** source-reconciled benchmark fixtures: 12 reconciled foundation fixtures and 5 new fixtures.

## Source reconciliation

- PDFs discovered: 17
- Canonical sources: 17
- Exact duplicates: 0
- Near-duplicates: 0
- Canonical selection: every unique mapped PDF is canonical for its inferred domain.

## Counts

- Benchmarks: 17
- Categories: 77
- Securities/references: 107
- Sources: 17
- By benchmark:
  - ai-data-center-networking-cabling: 3 categories; 4 securities/references
  - ai-power-supply-chain: 3 categories; 4 securities/references
  - crispr-ai-oncology: 3 categories; 4 securities/references
  - critical-infrastructure-cybersecurity: 7 categories; 10 securities/references
  - critical-minerals: 3 categories; 4 securities/references
  - crypto-adjacent-companies: 3 categories; 6 securities/references
  - defense-drones-counter-drone: 3 categories; 4 securities/references
  - ev-autonomous-driving: 3 categories; 4 securities/references
  - fintech: 10 categories; 15 securities/references
  - fusion-energy: 8 categories; 10 securities/references
  - glp1-obesity-drug-supply-chain: 9 categories; 11 securities/references
  - nuclear-power-ai-data-centers: 3 categories; 4 securities/references
  - retail-sector: 3 categories; 4 securities/references
  - robotics-humanoids: 3 categories; 4 securities/references
  - semiconductor-packaging: 3 categories; 4 securities/references
  - space-exploration: 3 categories; 4 securities/references
  - traditional-banking: 7 categories; 11 securities/references

## Private references

- crispr-ai-oncology: Insitro
- critical-infrastructure-cybersecurity: Dragos
- critical-infrastructure-cybersecurity: Claroty
- defense-drones-counter-drone: Anduril Industries
- fintech: Stripe
- fintech: Revolut
- fintech: Plaid
- fusion-energy: Commonwealth Fusion Systems
- fusion-energy: Helion Energy
- glp1-obesity-drug-supply-chain: CordenPharma
- glp1-obesity-drug-supply-chain: CTLT
- glp1-obesity-drug-supply-chain: Ro
- nuclear-power-ai-data-centers: TerraPower
- retail-sector: Aldi
- robotics-humanoids: Figure AI

## International references

- ai-data-center-networking-cabling: NOK
- crispr-ai-oncology: CRSP
- critical-minerals: LYC
- crypto-adjacent-companies: GLXY
- ev-autonomous-driving: MBLY
- fusion-energy: E
- glp1-obesity-drug-supply-chain: LONN
- nuclear-power-ai-data-centers: CCJ
- robotics-humanoids: FANUY
- semiconductor-packaging: ASX
- semiconductor-packaging: BESI

## Fund references

- critical-minerals: REMX
- crypto-adjacent-companies: IBIT
- nuclear-power-ai-data-centers: NLR
- robotics-humanoids: BOTZ
- space-exploration: ARKX
- traditional-banking: KRE

## Must-exclude records

- ai-power-supply-chain: CRM
- ev-autonomous-driving: FSRNQ
- traditional-banking: BLK

## Unresolved provenance and classifications

- ai-power-supply-chain: Salesforce - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- crispr-ai-oncology: Tempus AI - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- crispr-ai-oncology: Insitro - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- critical-minerals: Albemarle - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- critical-minerals: VanEck Rare Earth and Strategic Metals ETF - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- crypto-adjacent-companies: iShares Bitcoin Trust ETF - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- ev-autonomous-driving: Fisker - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- fintech: Fiserv - HUMAN REVIEW: verify current ticker because the source describes a 2025 ticker change.
- fintech: Chime Financial - HUMAN REVIEW: source reports a recent listing; verify ticker and status.
- fintech: Klarna Group - HUMAN REVIEW: source reports a recent listing; verify ticker and status.
- fusion-energy: General Fusion Group - HUMAN REVIEW: source reports a same-day listing; verify current listing status before use.
- fusion-energy: Trump Media & Technology Group - HUMAN REVIEW: merger completion and resulting exposure require verification.
- nuclear-power-ai-data-centers: TerraPower - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- nuclear-power-ai-data-centers: VanEck Uranium and Nuclear ETF - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- retail-sector: Aldi - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- robotics-humanoids: Figure AI - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- robotics-humanoids: Global X Robotics & Artificial Intelligence ETF - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- space-exploration: Rocket Lab USA - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.
- space-exploration: ARK Space Exploration & Innovation ETF - HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved.

## Cross-domain overlaps

- American Express (AXP): Traditional Banking and Fintech
- Capital One (COF): Traditional Banking and identified by the Fintech/Banking boundary
- Robinhood (HOOD): Fintech and Crypto
- PayPal (PYPL): Fintech and Crypto

The full PDF inventory and canonical source mapping are in `RCE_Benchmark_Corpus_Inventory.md`; machine-readable details are in `data/research/rce_benchmark_reconciliation_v0.2.json`.
