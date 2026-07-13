# RCE Benchmark Report: baseline-v0.1-providerfix

This report is deterministic benchmark instrumentation. It does not classify unexpected candidates as incorrect and does not claim improvement or regression.

- Execution date: 2026-07-13T20:16:27.544516+00:00
- Provider: openai
- Model: gpt-4.1-mini
- Prompt version: rce-multi-stage-artifact-pipeline-v0.1
- Benchmark corpus version(s): v0.2
- Runs: 17 (17 successful, 0 failed)

## Benchmark scores

| Benchmark | Status | Score | Latency (s) |
|---|---:|---:|---:|
| ai-data-center-networking-cabling | success | 0.6265 | 72.968 |
| ai-power-supply-chain | success | 0.5786 | 33.645 |
| crispr-ai-oncology | success | 0.5682 | 50.918 |
| critical-infrastructure-cybersecurity | success | 0.3567 | 71.243 |
| critical-minerals | success | 0.3633 | 281.668 |
| crypto-adjacent-companies | success | 0.5476 | 33.494 |
| defense-drones-counter-drone | success | 0.5524 | 49.886 |
| ev-autonomous-driving | success | 0.5428 | 27.276 |
| fintech | success | 0.3702 | 31.613 |
| fusion-energy | success | 0.2000 | 78.370 |
| glp1-obesity-drug-supply-chain | success | 0.2500 | 26.148 |
| nuclear-power-ai-data-centers | success | 0.1750 | 31.874 |
| retail-sector | success | 0.5414 | 61.407 |
| robotics-humanoids | success | 0.6111 | 41.745 |
| semiconductor-packaging | success | 0.3184 | 29.734 |
| space-exploration | success | 0.2342 | 102.689 |
| traditional-banking | success | 0.5238 | 68.095 |

## Aggregate score by metric

- candidate_validity: 0.1364
- category_coverage: 0.0651
- evidence_completeness: 0.0000
- listing_constraint_compliance: 0.6471
- must_exclude_compliance: 1.0000
- must_include_recall: 0.5863
- ranking_quality: 0.3232
- rationale_completeness: 0.0000
- schema_provider_integrity: 1.0000
- weighted_candidate_recall: 0.5724

## Missing must-include companies

- critical-infrastructure-cybersecurity: CSCO
- critical-minerals: MP
- fintech: FISV
- fintech: HOOD
- fusion-energy: GFUZ
- fusion-energy: AMSC
- glp1-obesity-drug-supply-chain: NVO
- glp1-obesity-drug-supply-chain: LLY
- nuclear-power-ai-data-centers: CEG
- semiconductor-packaging: AMKR
- space-exploration: RKLB
- space-exploration: SPCX
- traditional-banking: GS

## Must-exclude violations

- None recorded.

## Invalid candidates

- ai-power-supply-chain: PWR
- critical-infrastructure-cybersecurity: NERC (North American Electric Reliability Corporation)
- critical-infrastructure-cybersecurity: NIST (National Institute of Standards and Technology)
- critical-infrastructure-cybersecurity: ISA (International Society of Automation)
- critical-minerals: MP MATERIALS CORP
- defense-drones-counter-drone: EL,
- ev-autonomous-driving: LRCX
- ev-autonomous-driving: LRCX
- fintech: PYPL
- fintech: FRC
- fintech: FRC
- fusion-energy: LPI
- fusion-energy: LPI
- nuclear-power-ai-data-centers: Nuclear Energy Institute (NEI)
- nuclear-power-ai-data-centers: U.S. Nuclear Regulatory Commission (NRC)
- nuclear-power-ai-data-centers: Advanced Reactors and SMR Developers (e.g., NuScale Power, TerraPower)
- retail-sector: 7-ELEVEN
- robotics-humanoids: Boston Dynamics (Private)
- robotics-humanoids: Agility Robotics (Private)
- robotics-humanoids: SoftBank Robotics (Private)
- space-exploration: SpaceX (Private)
- space-exploration: Blue Origin (Private)
- space-exploration: Relativity Space (Private)
- space-exploration: Planet Labs (Private)
- space-exploration: Rocket Lab USA, Inc. (Private)

## Benchmarks requiring manual review

- ai-data-center-networking-cabling: MRVL
- ai-data-center-networking-cabling: CSCO
- ai-data-center-networking-cabling: LITE
- ai-data-center-networking-cabling: III
- ai-data-center-networking-cabling: PRTY
- ai-data-center-networking-cabling: GLBL
- ai-data-center-networking-cabling: FNSR
- ai-data-center-networking-cabling: AMBA
- ai-data-center-networking-cabling: QCOM
- ai-data-center-networking-cabling: TER
- ai-data-center-networking-cabling: FLIR
- ai-data-center-networking-cabling: HUBB
- ai-data-center-networking-cabling: AMPL
- ai-data-center-networking-cabling: TE
- ai-power-supply-chain: CEG
- ai-power-supply-chain: PCT
- ai-power-supply-chain: NEE
- ai-power-supply-chain: ABB
- ai-power-supply-chain: GE
- ai-power-supply-chain: FLIR
- ai-power-supply-chain: SI
- ai-power-supply-chain: SPWR
- ai-power-supply-chain: KR
- ai-power-supply-chain: ARE
- crispr-ai-oncology: EDIT
- crispr-ai-oncology: BEAM
- crispr-ai-oncology: NTLA
- crispr-ai-oncology: EXAI
- crispr-ai-oncology: GH
- crispr-ai-oncology: ILMN
- crispr-ai-oncology: TMO
- crispr-ai-oncology: REGN
- crispr-ai-oncology: BNTX
- crispr-ai-oncology: NVTA
- crispr-ai-oncology: IQV
- crispr-ai-oncology: VTRS
- crispr-ai-oncology: ARRY
- critical-infrastructure-cybersecurity: ZS
- critical-infrastructure-cybersecurity: CYBR
- critical-infrastructure-cybersecurity: TENB
- critical-infrastructure-cybersecurity: RPD
- critical-infrastructure-cybersecurity: MSFT
- critical-infrastructure-cybersecurity: IBM
- critical-infrastructure-cybersecurity: GLBL
- critical-infrastructure-cybersecurity: ENBL
- critical-infrastructure-cybersecurity: NERC (North American Electric Reliability Corporation)
- critical-infrastructure-cybersecurity: NIST (National Institute of Standards and Technology)
- critical-infrastructure-cybersecurity: ISA (International Society of Automation)
- critical-minerals: LAC
- critical-minerals: SQM
- critical-minerals: MP MATERIALS CORP
- critical-minerals: LKE
- critical-minerals: FMC
- critical-minerals: ION
- critical-minerals: BATT
- critical-minerals: GLDX
- critical-minerals: NEM
- critical-minerals: NIOBF
- critical-minerals: SQM-B
- critical-minerals: SLS
- critical-minerals: QURE
- critical-minerals: VEA
- crypto-adjacent-companies: RIOT
- crypto-adjacent-companies: HUT
- crypto-adjacent-companies: BITF
- crypto-adjacent-companies: BTBT
- crypto-adjacent-companies: HIVE
- crypto-adjacent-companies: GTH
- crypto-adjacent-companies: EXCH
- crypto-adjacent-companies: BITW
- crypto-adjacent-companies: BLOK
- crypto-adjacent-companies: CRPT
- crypto-adjacent-companies: SQ
- crypto-adjacent-companies: NVDA
- crypto-adjacent-companies: AMD
- defense-drones-counter-drone: NOC
- defense-drones-counter-drone: LMT
- defense-drones-counter-drone: RTX
- defense-drones-counter-drone: GD
- defense-drones-counter-drone: HWM
- defense-drones-counter-drone: TXT
- defense-drones-counter-drone: SAIC
- defense-drones-counter-drone: VTN
- defense-drones-counter-drone: KR
- defense-drones-counter-drone: BDSI
- defense-drones-counter-drone: MRCY
- defense-drones-counter-drone: IOT
- defense-drones-counter-drone: DMTK
- defense-drones-counter-drone: FLIR
- defense-drones-counter-drone: BA
- defense-drones-counter-drone: HERD
- defense-drones-counter-drone: EL,
- defense-drones-counter-drone: SAAB-B.ST
- defense-drones-counter-drone: HXL
- defense-drones-counter-drone: MAXR
- defense-drones-counter-drone: FLT
- ev-autonomous-driving: GM
- ev-autonomous-driving: F
- ev-autonomous-driving: NVDA
- ev-autonomous-driving: MRCY
- ev-autonomous-driving: LIDR
- ev-autonomous-driving: ROK
- ev-autonomous-driving: ADI
- ev-autonomous-driving: LRCX
- ev-autonomous-driving: AZTA
- ev-autonomous-driving: LRCX
- ev-autonomous-driving: XLNX
- ev-autonomous-driving: STM
- ev-autonomous-driving: QRVO
- ev-autonomous-driving: VLY
- ev-autonomous-driving: AAPL
- ev-autonomous-driving: GOOG
- ev-autonomous-driving: MOT
- ev-autonomous-driving: HALL
- fintech: SQ
- fintech: UPST
- fintech: SOFI
- fintech: N26
- fintech: BMY
- fintech: FRC
- fintech: SCHW
- fintech: MORN
- fintech: ET
- fintech: FRC
- fintech: PGTI
- fusion-energy: LPI
- fusion-energy: HVN
- fusion-energy: MCW
- fusion-energy: TSLA
- fusion-energy: LPI
- fusion-energy: ASML
- fusion-energy: ST
- fusion-energy: ABB
- fusion-energy: GE
- fusion-energy: THER
- fusion-energy: ITER
- fusion-energy: NUCL
- fusion-energy: APHA
- fusion-energy: MTOR
- glp1-obesity-drug-supply-chain: MRNA
- glp1-obesity-drug-supply-chain: AMGN
- glp1-obesity-drug-supply-chain: RGEN
- glp1-obesity-drug-supply-chain: ALK
- glp1-obesity-drug-supply-chain: CDMO
- glp1-obesity-drug-supply-chain: CALT
- glp1-obesity-drug-supply-chain: BIIB
- glp1-obesity-drug-supply-chain: PKG
- glp1-obesity-drug-supply-chain: MRTX
- glp1-obesity-drug-supply-chain: VTRS
- glp1-obesity-drug-supply-chain: THRM
- glp1-obesity-drug-supply-chain: LZ
- glp1-obesity-drug-supply-chain: PFE
- glp1-obesity-drug-supply-chain: SGEN
- glp1-obesity-drug-supply-chain: CNC
- glp1-obesity-drug-supply-chain: REPH
- glp1-obesity-drug-supply-chain: COO
- glp1-obesity-drug-supply-chain: ZBH
- glp1-obesity-drug-supply-chain: IQV
- glp1-obesity-drug-supply-chain: HUBG
- nuclear-power-ai-data-centers: NEE
- nuclear-power-ai-data-centers: EXC
- nuclear-power-ai-data-centers: DUK
- nuclear-power-ai-data-centers: XEL
- nuclear-power-ai-data-centers: GE
- nuclear-power-ai-data-centers: BWXT
- nuclear-power-ai-data-centers: CBI
- nuclear-power-ai-data-centers: VRTS
- nuclear-power-ai-data-centers: ARE
- nuclear-power-ai-data-centers: ETN
- nuclear-power-ai-data-centers: AEP
- nuclear-power-ai-data-centers: PWR
- nuclear-power-ai-data-centers: Nuclear Energy Institute (NEI)
- nuclear-power-ai-data-centers: U.S. Nuclear Regulatory Commission (NRC)
- nuclear-power-ai-data-centers: Advanced Reactors and SMR Developers (e.g., NuScale Power, TerraPower)
- nuclear-power-ai-data-centers: HOLX
- nuclear-power-ai-data-centers: AES
- nuclear-power-ai-data-centers: MSEX
- nuclear-power-ai-data-centers: SCHL
- nuclear-power-ai-data-centers: ABB
- nuclear-power-ai-data-centers: ZAYO
- retail-sector: M
- retail-sector: JWN
- retail-sector: TGT
- retail-sector: DG
- retail-sector: KR
- retail-sector: 7-ELEVEN
- retail-sector: LULU
- retail-sector: ANF
- retail-sector: GPS
- retail-sector: RL
- retail-sector: KORS
- retail-sector: BABA
- retail-sector: ETSY
- retail-sector: BBY
- retail-sector: HD
- retail-sector: LOW
- retail-sector: TJX
- retail-sector: BURL
- retail-sector: EBAY
- retail-sector: CVS
- retail-sector: WBA
- robotics-humanoids: IRBT
- robotics-humanoids: ABB
- robotics-humanoids: ROBO
- robotics-humanoids: LBRDK
- robotics-humanoids: DHR
- robotics-humanoids: HON
- robotics-humanoids: Boston Dynamics (Private)
- robotics-humanoids: Agility Robotics (Private)
- robotics-humanoids: SoftBank Robotics (Private)
- robotics-humanoids: MCHP
- robotics-humanoids: NVDA
- robotics-humanoids: INTC
- robotics-humanoids: YASKY
- robotics-humanoids: KUKAY
- robotics-humanoids: SYNA
- robotics-humanoids: MELI
- semiconductor-packaging: ASE
- semiconductor-packaging: SPIL
- semiconductor-packaging: KYEC
- semiconductor-packaging: UREN
- semiconductor-packaging: FLEX
- semiconductor-packaging: TSM
- semiconductor-packaging: AMAT
- semiconductor-packaging: TER
- semiconductor-packaging: SHI
- semiconductor-packaging: KINS
- semiconductor-packaging: JBL
- semiconductor-packaging: TXN
- semiconductor-packaging: QRVO
- semiconductor-packaging: NOVA
- semiconductor-packaging: SMIT
- semiconductor-packaging: MMSI
- space-exploration: SPCE
- space-exploration: MAXR
- space-exploration: TDW
- space-exploration: MAXAR
- space-exploration: BRDS
- space-exploration: LMT
- space-exploration: BA
- space-exploration: NOC
- space-exploration: HWM
- space-exploration: SpaceX (Private)
- space-exploration: Blue Origin (Private)
- space-exploration: Relativity Space (Private)
- space-exploration: Planet Labs (Private)
- space-exploration: Rocket Lab USA, Inc. (Private)
- space-exploration: ACPW
- space-exploration: SES
- space-exploration: TWO
- traditional-banking: WFC
- traditional-banking: PNC
- traditional-banking: TFC
- traditional-banking: KEY
- traditional-banking: FITB
- traditional-banking: KBE
- traditional-banking: KBWB

## Category gaps

- ai-data-center-networking-cabling: Networking silicon
- ai-data-center-networking-cabling: Optical and cabling
- ai-power-supply-chain: Electrical and power management
- ai-power-supply-chain: Grid construction
- crispr-ai-oncology: Gene editing
- crispr-ai-oncology: AI oncology platforms
- critical-infrastructure-cybersecurity: OT / ICS security
- critical-infrastructure-cybersecurity: Industrial networking and visibility
- critical-infrastructure-cybersecurity: Physical and communications security
- critical-infrastructure-cybersecurity: Broad enterprise cybersecurity
- critical-infrastructure-cybersecurity: Monitoring and DDoS protection
- critical-infrastructure-cybersecurity: Vulnerability management
- critical-infrastructure-cybersecurity: Identity and data security
- critical-minerals: Producers
- critical-minerals: Processing and refining
- critical-minerals: Diversified funds
- crypto-adjacent-companies: Exchanges and infrastructure
- crypto-adjacent-companies: Mining and compute
- crypto-adjacent-companies: Crypto funds
- defense-drones-counter-drone: Drone platforms
- ev-autonomous-driving: Vehicle platforms
- ev-autonomous-driving: Autonomy and sensors
- fintech: Payment networks and card rails
- fintech: Payment processors
- fintech: Core financial infrastructure
- fintech: Digital wallets
- fintech: Neobanks
- fintech: Wealth and trading platforms
- fintech: Private IPO candidates
- fintech: Embedded finance
- fintech: Crypto overlap
- fusion-energy: Public fusion developers
- fusion-energy: HTS magnets and superconductors
- fusion-energy: Cryogenic and industrial gases
- fusion-energy: Strategic investors
- fusion-energy: Power-offtake partners
- fusion-energy: Private fusion leaders
- fusion-energy: Fuel-cycle infrastructure
- fusion-energy: Power electronics
- glp1-obesity-drug-supply-chain: Approved drug leaders
- glp1-obesity-drug-supply-chain: Clinical-stage challengers
- glp1-obesity-drug-supply-chain: Peptide manufacturers and CDMOs
- glp1-obesity-drug-supply-chain: Delivery devices
- glp1-obesity-drug-supply-chain: Packaging and fill-finish
- glp1-obesity-drug-supply-chain: Telehealth and distribution
- glp1-obesity-drug-supply-chain: Secondary effects
- glp1-obesity-drug-supply-chain: Biosimilar and generic opportunities
- glp1-obesity-drug-supply-chain: Private supply-chain participants
- nuclear-power-ai-data-centers: Nuclear generation
- nuclear-power-ai-data-centers: Advanced reactors and fuel
- nuclear-power-ai-data-centers: Broad clean-energy funds
- retail-sector: Mass and warehouse retail
- retail-sector: Specialty and digital retail
- retail-sector: Private retailers
- robotics-humanoids: Humanoid platforms
- robotics-humanoids: Robotics funds
- semiconductor-packaging: Advanced packaging equipment
- semiconductor-packaging: Assembly and test
- semiconductor-packaging: Integrated chip designers
- space-exploration: Launch and spacecraft
- space-exploration: Satellite infrastructure
- space-exploration: Space funds
- traditional-banking: Money-center banks
- traditional-banking: Investment banks and capital markets
- traditional-banking: Regional and super-regional banks
- traditional-banking: Custody and trust banks
- traditional-banking: Card-issuing bank holding companies
- traditional-banking: Community banks
- traditional-banking: Asset managers

## Listing violations

- ai-power-supply-chain: PWR (candidate_entity_validation)
- critical-infrastructure-cybersecurity: NERC (North American Electric Reliability Corporation) (candidate_entity_validation)
- critical-infrastructure-cybersecurity: NIST (National Institute of Standards and Technology) (candidate_entity_validation)
- critical-infrastructure-cybersecurity: ISA (International Society of Automation) (candidate_entity_validation)
- critical-minerals: MP MATERIALS CORP (candidate_entity_validation)
- defense-drones-counter-drone: EL, (candidate_entity_validation)
- ev-autonomous-driving: LRCX (candidate_entity_validation)
- ev-autonomous-driving: LRCX (candidate_entity_validation)
- fintech: PYPL (candidate_entity_validation)
- fintech: FRC (candidate_entity_validation)
- fintech: FRC (candidate_entity_validation)
- fusion-energy: LPI (candidate_entity_validation)
- fusion-energy: LPI (candidate_entity_validation)
- nuclear-power-ai-data-centers: Nuclear Energy Institute (NEI) (candidate_entity_validation)
- nuclear-power-ai-data-centers: U.S. Nuclear Regulatory Commission (NRC) (candidate_entity_validation)
- nuclear-power-ai-data-centers: Advanced Reactors and SMR Developers (e.g., NuScale Power, TerraPower) (candidate_entity_validation)
- retail-sector: 7-ELEVEN (candidate_entity_validation)
- robotics-humanoids: Boston Dynamics (Private) (candidate_entity_validation)
- robotics-humanoids: Agility Robotics (Private) (candidate_entity_validation)
- robotics-humanoids: SoftBank Robotics (Private) (candidate_entity_validation)
- space-exploration: SpaceX (Private) (candidate_entity_validation)
- space-exploration: Blue Origin (Private) (candidate_entity_validation)
- space-exploration: Relativity Space (Private) (candidate_entity_validation)
- space-exploration: Planet Labs (Private) (candidate_entity_validation)
- space-exploration: Rocket Lab USA, Inc. (Private) (candidate_entity_validation)

## Parser and provider issues

- None recorded.

## Latency, token usage, and cost

- Latency seconds: min 26.148, p50 49.886, p95 102.689, max 281.668
- Token usage: input 49140, cached input 0, output 43529, reasoning 0
- Estimated API cost: $0.089302

## Recurring failure patterns

- Review category gaps, missing expected candidates, provider/parser issues, and unresolved unexpected candidates above. No causal claim is made automatically.

## Known limitations

- The corpus is reviewed reference data, not absolute truth.
- Unexpected candidates remain unresolved until human review.
- Structured candidate evidence is not present in the current artifact schema and is reported without failing runs.
- Human-review scores remain separate from the deterministic overall score.
