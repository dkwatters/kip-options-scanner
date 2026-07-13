"""Reconcile canonical RCE fixtures and generate corpus reports (v0.2)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.rce_benchmark_corpus import DOMAIN_BY_FILENAME, inventory_pdfs, source_page_for_company

PDF_DIR = ROOT / "docs/research/benchmarks"
FIXTURE_DIR = ROOT / "tests/fixtures/rce_benchmarks"
SOURCE_DATE = "2026-07-10"


def category(name, role, importance, status="core", notes="Source-defined research-map category."):
    return {"category_name": name, "category_role": role, "importance": importance, "expected_status": status, "notes": notes}


def security(ticker, name, category_name, expectation, importance, role, *, exchange=None,
             region="US", status="public", page=None, notes=None):
    reference_identifier = None
    if expectation == "private_reference" and not ticker:
        slug = "-".join(name.casefold().replace("&", " and ").split())
        reference_identifier = f"{status}-company:{slug}"
    return {
        "ticker": ticker, "company_name": name, "exchange": exchange,
        "reference_identifier": reference_identifier,
        "listing_region": region, "public_status": status, "category_name": category_name,
        "expectation": expectation, "importance": importance, "role_summary": role,
        "evidence_summary": f"Canonical source identifies {name} in this role on page {page}." if page else f"Canonical source identifies {name} in this role.",
        "notes": notes or "Classification follows the canonical source and benchmark rubric.",
    }


NEW = {
"critical infra cybersecurity companies.pdf": {
 "id":"critical-infrastructure-cybersecurity", "name":"Critical Infrastructure Cybersecurity",
 "question":"Which public companies and reference entities matter when researching cybersecurity for critical infrastructure?",
 "description":"QA reference spanning OT/ICS, industrial visibility, physical communications, monitoring, vulnerability, identity, and data security.", "domain":"Cybersecurity", "difficulty":"advanced",
 "categories":[
  category("OT / ICS security","Security for SCADA, industrial control systems, and operational technology",5),
  category("Industrial networking and visibility","Secure converged industrial networking and OT visibility",5),
  category("Physical and communications security","Resilient communications and integrated physical/cyber protection",4),
  category("Broad enterprise cybersecurity","General endpoint, network, cloud, and zero-trust platforms",3,"adjacent"),
  category("Monitoring and DDoS protection","Infrastructure-scale network monitoring and denial-of-service defense",4),
  category("Vulnerability management","Exposure assessment, scanning, and compliance",4),
  category("Identity and data security","Identity, data posture, and hybrid-cloud protection",3,"adjacent"),
 ],
 "securities":[
  security("PANW","Palo Alto Networks","OT / ICS security","must_include",5,"Dedicated OT security within a broad platform",exchange="NASDAQ",page=1),
  security("FTNT","Fortinet","OT / ICS security","should_include",4,"Enterprise and industrial network security",exchange="NASDAQ",page=1),
  security("CSCO","Cisco Systems","Industrial networking and visibility","must_include",5,"Secure industrial networking and visibility",exchange="NASDAQ",page=1),
  security(None,"Dragos","OT / ICS security","private_reference",5,"Specialized OT security vendor",status="private",region=None,page=1),
  security(None,"Claroty","OT / ICS security","private_reference",5,"Specialized cyber-physical security vendor",status="private",region=None,page=1),
  security("MSI","Motorola Solutions","Physical and communications security","should_include",4,"Resilient public-safety communications and physical security",exchange="NYSE",page=1),
  security("CRWD","CrowdStrike","Broad enterprise cybersecurity","acceptable",3,"Endpoint detection platform adjacent to OT",exchange="NASDAQ",page=2),
  security("NTCT","Netscout Systems","Monitoring and DDoS protection","should_include",4,"Carrier-grade monitoring and DDoS defense",exchange="NASDAQ",page=2),
  security("QLYS","Qualys","Vulnerability management","should_include",4,"Cloud vulnerability and compliance management",exchange="NASDAQ",page=2),
  security("OKTA","Okta","Identity and data security","acceptable",3,"Identity layer for zero-trust architectures",exchange="NASDAQ",page=2),
 ]},
"fusion energy companies.pdf": {
 "id":"fusion-energy", "name":"Fusion Energy", "question":"Which public companies and reference entities matter across the fusion-energy value chain?",
 "description":"QA reference for fusion developers, enabling suppliers, strategic partners, and private leaders.", "domain":"Energy technology", "difficulty":"advanced",
 "categories":[
  category("Public fusion developers","Publicly listed fusion reactor developers",5), category("HTS magnets and superconductors","REBCO tape and magnet systems",5),
  category("Cryogenic and industrial gases","Cryogenic systems required by fusion plants",4), category("Strategic investors","Corporate equity investors in fusion developers",3,"adjacent"),
  category("Power-offtake partners","Companies contracting for future fusion output",4), category("Private fusion leaders","Non-public reactor developers",5),
  category("Fuel-cycle infrastructure","Tritium and fuel handling",3,"optional"), category("Power electronics","Grid integration and conversion equipment",3,"optional"),
 ],
 "securities":[
  security("GFUZ","General Fusion Group","Public fusion developers","must_include",5,"Public magnetized-target fusion developer",exchange="NASDAQ",page=1,notes="HUMAN REVIEW: source reports a same-day listing; verify current listing status before use."),
  security("DJT","Trump Media & Technology Group","Public fusion developers","should_include",4,"Proposed public route for TAE Technologies",exchange="NASDAQ",page=1,notes="HUMAN REVIEW: merger completion and resulting exposure require verification."),
  security("AMSC","American Superconductor","HTS magnets and superconductors","must_include",5,"Public HTS conductor supplier",exchange="NASDAQ",page=1),
  security("BRKR","Bruker Corporation","HTS magnets and superconductors","should_include",4,"Superconductor and magnet-system supplier",exchange="NASDAQ",page=1),
  security("LIN","Linde plc","Cryogenic and industrial gases","should_include",4,"Large-scale cryogenic systems supplier",exchange="NASDAQ",page=2),
  security("GOOGL","Alphabet","Power-offtake partners","acceptable",3,"Investor and prospective fusion power buyer",exchange="NASDAQ",page=2),
  security("E","Eni","Strategic investors","international_reference",3,"CFS investor and offtake partner",exchange="NYSE",region="International",page=2),
  security("MSFT","Microsoft","Power-offtake partners","should_include",4,"Helion power-purchase counterparty",exchange="NASDAQ",page=2),
  security(None,"Commonwealth Fusion Systems","Private fusion leaders","private_reference",5,"Private SPARC/ARC fusion leader",status="private",region=None,page=2),
  security(None,"Helion Energy","Private fusion leaders","private_reference",5,"Private fusion developer with Microsoft offtake",status="private",region=None,page=2),
 ]},
"glp1 supply chain companies.pdf": {
 "id":"glp1-obesity-drug-supply-chain", "name":"GLP-1 / Obesity Drug Supply Chain", "question":"Which public companies and reference entities matter across the GLP-1 and obesity-drug supply chain?",
 "description":"QA reference from approved drugs through manufacturing, devices, distribution, and secondary effects.", "domain":"Biopharma supply chain", "difficulty":"advanced",
 "categories":[
  category("Approved drug leaders","Approved GLP-1 and obesity medicines",5), category("Clinical-stage challengers","Pipeline-stage differentiated therapies",4),
  category("Peptide manufacturers and CDMOs","Commercial peptide manufacturing capacity",5), category("Delivery devices","Syringes and injection systems",4),
  category("Packaging and fill-finish","Containment and sterile finishing",4), category("Telehealth and distribution","Patient access and fulfillment",3,"adjacent"),
  category("Secondary effects","Downstream beneficiary and loser industries",2,"optional"), category("Biosimilar and generic opportunities","Post-patent lower-cost entrants",3,"optional"),
  category("Private supply-chain participants","Non-public manufacturing and distribution participants",4),
 ],
 "securities":[
  security("NVO","Novo Nordisk","Approved drug leaders","must_include",5,"Semaglutide market leader",exchange="NYSE",region="International",page=1),
  security("LLY","Eli Lilly","Approved drug leaders","must_include",5,"Tirzepatide market leader",exchange="NYSE",page=1),
  security("VKTX","Viking Therapeutics","Clinical-stage challengers","should_include",4,"Dual-agonist clinical challenger",exchange="NASDAQ",page=1),
  security("GPCR","Structure Therapeutics","Clinical-stage challengers","should_include",4,"Oral small-molecule challenger",exchange="NASDAQ",page=1),
  security("LONN","Lonza Group","Peptide manufacturers and CDMOs","international_reference",4,"Global peptide CDMO",exchange="SIX",region="International",page=2),
  security("WST","West Pharmaceutical Services","Packaging and fill-finish","should_include",4,"Injectable containment components",exchange="NYSE",page=2),
  security("STVN","Stevanato Group","Delivery devices","should_include",4,"Syringes and delivery systems",exchange="NYSE",region="International",page=2),
  security("HIMS","Hims & Hers Health","Telehealth and distribution","acceptable",3,"Direct-to-consumer access and fulfillment",exchange="NYSE",page=2),
  security(None,"CordenPharma","Private supply-chain participants","private_reference",4,"Private peptide-capacity supplier",status="private",region=None,page=2),
  security("CTLT","Catalent","Private supply-chain participants","private_reference",3,"Acquired fill-finish reference",status="acquired",exchange="NYSE",page=2),
  security(None,"Ro","Telehealth and distribution","private_reference",3,"Private telehealth competitor",status="private",region=None,page=2),
 ]},
"traditional banking companies.pdf": {
 "id":"traditional-banking", "name":"Traditional Banking", "question":"Which public companies and reference entities matter across traditional U.S. banking business models?",
 "description":"QA reference separating money centers, capital markets, regional, custody, and card-issuing banks.", "domain":"Financial services", "difficulty":"intermediate",
 "categories":[
  category("Money-center banks","Large global systemically important banks",5), category("Investment banks and capital markets","Advisory, underwriting, and trading franchises",4),
  category("Regional and super-regional banks","Geographically concentrated lending banks",4), category("Custody and trust banks","Fee-based asset servicing and custody",4),
  category("Card-issuing bank holding companies","Banks driven materially by cards and networks",4), category("Community banks","Long-tail smaller depositories",2,"optional"),
  category("Asset managers","AUM-fee businesses outside the banking boundary",2,"adjacent"),
 ],
 "securities":[
  security("JPM","JPMorgan Chase","Money-center banks","must_include",5,"Largest diversified U.S. bank",exchange="NYSE",page=1),
  security("BAC","Bank of America","Money-center banks","must_include",5,"Major U.S. money-center bank",exchange="NYSE",page=1),
  security("C","Citigroup","Money-center banks","should_include",4,"Global turnaround bank",exchange="NYSE",page=1),
  security("GS","Goldman Sachs","Investment banks and capital markets","must_include",5,"Capital-markets leader",exchange="NYSE",page=1),
  security("MS","Morgan Stanley","Investment banks and capital markets","should_include",4,"Investment bank and wealth manager",exchange="NYSE",page=1),
  security("USB","US Bancorp","Regional and super-regional banks","should_include",4,"Large super-regional bank",exchange="NYSE",page=2),
  security("STT","State Street","Custody and trust banks","should_include",4,"Global custody and asset servicing bank",exchange="NYSE",page=2),
  security("COF","Capital One Financial","Card-issuing bank holding companies","must_include",5,"Card issuer, bank, and Discover network owner",exchange="NYSE",page=2),
  security("AXP","American Express","Card-issuing bank holding companies","must_include",5,"Closed-loop network and issuing bank",exchange="NYSE",page=3),
  security("KRE","SPDR S&P Regional Banking ETF","Regional and super-regional banks","fund_reference",3,"Broad regional-bank comparison vehicle",exchange="NYSE Arca",page=2),
  security("BLK","BlackRock","Asset managers","must_exclude",2,"Asset manager outside lending-bank boundary",exchange="NYSE",page=3),
 ]},
"fintech companies.pdf": {
 "id":"fintech", "name":"Fintech", "question":"Which public companies and reference entities matter across payments, digital banking, BNPL, and wealth-platform fintech?",
 "description":"QA reference separating payment rails, processing, wallets, neobanks, BNPL, platforms, and private infrastructure.", "domain":"Financial technology", "difficulty":"intermediate",
 "categories":[
  category("Payment networks and card rails","Global card-network infrastructure",5), category("Payment processors","Merchant acquiring and transaction processing",5),
  category("Core financial infrastructure","Banking technology and issuing APIs",4), category("Digital wallets","Consumer checkout and wallet ecosystems",4),
  category("Neobanks","Digital-first banking platforms",4), category("BNPL","Point-of-sale installment credit",4),
  category("Wealth and trading platforms","Digital brokerage and investing",4), category("Private IPO candidates","Late-stage non-public fintechs",3),
  category("Embedded finance","B2B spend, payroll, and financial APIs",3,"adjacent"), category("Crypto overlap","Fintechs with material crypto activity",3,"adjacent"),
 ],
 "securities":[
  security("V","Visa","Payment networks and card rails","must_include",5,"Dominant global card network",exchange="NYSE",page=1),
  security("MA","Mastercard","Payment networks and card rails","must_include",5,"Major global card network",exchange="NYSE",page=1),
  security("AXP","American Express","Payment networks and card rails","should_include",4,"Closed-loop network and issuing bank",exchange="NYSE",page=1),
  security("FISV","Fiserv","Payment processors","must_include",5,"Core banking, processing, and merchant platform",exchange="NASDAQ",page=1,notes="HUMAN REVIEW: verify current ticker because the source describes a 2025 ticker change."),
  security("GPN","Global Payments","Payment processors","should_include",4,"Merchant acquiring and payments technology",exchange="NYSE",page=1),
  security("PYPL","PayPal","Digital wallets","must_include",5,"Digital wallet, checkout, and crypto-overlap platform",exchange="NASDAQ",page=1),
  security("COF","Capital One Financial","Core financial infrastructure","acceptable",3,"Bank/fintech crossover and acquirer of Brex card-program assets",exchange="NYSE",page=3),
  security("XYZ","Block","Digital wallets","should_include",4,"Cash App and Square ecosystem",exchange="NYSE",page=2),
  security("CHYM","Chime Financial","Neobanks","should_include",4,"Digital-first consumer banking platform",exchange="NASDAQ",page=2,notes="HUMAN REVIEW: source reports a recent listing; verify ticker and status."),
  security("AFRM","Affirm Holdings","BNPL","must_include",5,"Public BNPL leader",exchange="NASDAQ",page=2),
  security("KLAR","Klarna Group","BNPL","should_include",4,"Global BNPL platform",exchange="NYSE",region="International",page=2,notes="HUMAN REVIEW: source reports a recent listing; verify ticker and status."),
  security("HOOD","Robinhood","Wealth and trading platforms","must_include",5,"Retail brokerage with crypto overlap",exchange="NASDAQ",page=3),
  security(None,"Stripe","Private IPO candidates","private_reference",5,"Private payments-infrastructure leader",status="private",region=None,page=3),
  security(None,"Revolut","Private IPO candidates","private_reference",4,"Private neobank and trading platform",status="private",region=None,page=3),
  security(None,"Plaid","Embedded finance","private_reference",4,"Private financial-data infrastructure provider",status="private",region=None,page=3),
 ]},
}


def reconcile_existing(records):
    fixture_to_pdf = {fixture: name for name, (_, fixture) in DOMAIN_BY_FILENAME.items()}
    hashes = {r.filename: r.sha256 for r in records}
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        if path.name not in fixture_to_pdf:
            continue
        pdf_name = fixture_to_pdf[path.name]
        pdf_path = PDF_DIR / pdf_name
        doc = json.loads(path.read_text(encoding="utf-8"))
        meta = doc["benchmark"]
        meta.update({"benchmark_status":"source_reconciled", "version":"v0.2", "source_document":pdf_name,
                     "source_date":SOURCE_DATE, "reviewed_by":"RCE benchmark corpus source reconciliation v0.2",
                     "review_notes":"Reconciled to the canonical repository PDF. Security records absent from the source are retained with human-review flags."})
        unresolved = 0
        for row in doc["securities"]:
            page = source_page_for_company(pdf_path, row.get("company_name") or "")
            if page:
                row["evidence_summary"] = f"Canonical source identifies {row['company_name']} in the stated thematic role on page {page}."
                row["notes"] = f"Source page {page}; classification retained under the benchmark rubric."
            else:
                unresolved += 1
                row["notes"] = "HUMAN REVIEW: entity was retained from the foundation fixture but was not located in the canonical PDF; classification and provenance remain unresolved."
                row["evidence_summary"] = "Not located in the canonical PDF during v0.2 reconciliation; retained without inventing source support."
        if meta["benchmark_id"] == "crypto-adjacent-companies":
            overlap = [
                security("HOOD", "Robinhood", doc["categories"][0]["category_name"], "should_include", 4, "Retail brokerage with material crypto trading exposure", exchange="NASDAQ", page=2),
                security("PYPL", "PayPal", doc["categories"][0]["category_name"], "acceptable", 3, "Payments platform with crypto and stablecoin exposure", exchange="NASDAQ", page=2),
            ]
            present = {row.get("ticker") for row in doc["securities"]}
            doc["securities"].extend(row for row in overlap if row["ticker"] not in present)
        meta["benchmark_status"] = "source_reconciled" if unresolved == 0 else "source_reconciled_pending_human_review"
        doc["benchmark_caveats"] = [
            "This benchmark is a QA/reference artifact, not ground truth or an investable universe.",
            "Company status, listing, and thematic relevance can change and require versioned review.",
            f"{unresolved} security record(s) require human review because they were not located in the canonical source." if unresolved else "All retained security records were located in the canonical source PDF.",
        ]
        doc["sources"] = [{"source_document":pdf_name,"source_page":f"1-{r.page_count}","source_section":"Entire canonical reference list",
                           "source_date":SOURCE_DATE,"source_notes":"Canonical repository PDF; page-level security citations are recorded in evidence summaries.","source_hash":hashes[pdf_name]} for r in records if r.filename == pdf_name]
        path.write_text(json.dumps(doc, indent=2)+"\n", encoding="utf-8")


def add_new(records):
    hashes = {r.filename: r for r in records}
    for pdf_name, spec in NEW.items():
        rec = hashes[pdf_name]
        doc = {"schema_version":"1.0","benchmark":{
            "benchmark_id":spec["id"],"benchmark_name":spec["name"],"research_question":spec["question"],"description":spec["description"],
            "domain":spec["domain"],"difficulty":spec["difficulty"],"benchmark_status":"source_reconciled","version":"v0.2",
            "source_document":pdf_name,"source_date":SOURCE_DATE,"reviewed_by":"RCE benchmark corpus source reconciliation v0.2",
            "review_notes":"Canonical fixture derived from the repository PDF; explicit human-review flags preserve uncertain time-sensitive classifications."},
            "categories":spec["categories"],"securities":spec["securities"],
            "benchmark_caveats":["This is a QA/reference artifact, not ground truth or an investable universe.","Listing status and thematic relevance require versioned review.","HUMAN REVIEW notes identify classifications requiring external confirmation."],
            "sources":[{"source_document":pdf_name,"source_page":f"1-{rec.page_count}","source_section":"Entire canonical reference list","source_date":SOURCE_DATE,
                        "source_notes":"Canonical repository PDF; page-level security citations appear in evidence summaries.","source_hash":rec.sha256}]}
        (FIXTURE_DIR / DOMAIN_BY_FILENAME[pdf_name][1]).write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")


def reports(records, duplicates):
    fixtures=[json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURE_DIR.glob("*.json"))]
    unresolved=[]
    for d in fixtures:
        for s in d["securities"]:
            if "HUMAN REVIEW" in (s.get("notes") or ""):
                unresolved.append({"benchmark_id":d["benchmark"]["benchmark_id"],"company_name":s.get("company_name"),"issue":s["notes"]})
    expectations=Counter(s["expectation"] for d in fixtures for s in d["securities"])
    counts={"benchmarks":len(fixtures),"categories":sum(len(d["categories"]) for d in fixtures),"securities_and_references":sum(len(d["securities"]) for d in fixtures),"sources":sum(len(d["sources"]) for d in fixtures),"expectations":dict(sorted(expectations.items()))}
    report={"report_version":"v0.2","generated_from":"docs/research/benchmarks","inventory":[r.as_dict() for r in records],"duplicates":duplicates,
            "canonical_sources":{r.domain:r.filename for r in records if r.canonical_source},"reconciled_existing_fixtures":12,"added_fixtures":5,
            "counts":counts,"unresolved_provenance":[x for x in unresolved if "not located" in x["issue"]],"unresolved_classification_review":unresolved,
            "cross_domain_overlaps":{"AXP":["traditional-banking","fintech"],"COF":["traditional-banking","fintech (source overlap; not duplicated in minimal fixture)"],"HOOD":["fintech","crypto-adjacent-companies"],"PYPL":["fintech","crypto-adjacent-companies"]}}
    out=ROOT/"data/research/rce_benchmark_reconciliation_v0.2.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# RCE Benchmark Corpus Inventory","",f"Generated for reconciliation v0.2. Discovered {len(records)} PDFs.","", "| Filename | Domain | Pages | Bytes | SHA-256 | Duplicate status | Canonical | Fixture | Reconciliation |","|---|---|---:|---:|---|---|---|---|---|"]
    for r in records: lines.append(f"| {r.filename} | {r.domain} | {r.page_count} | {r.file_size} | `{r.sha256}` | {r.duplicate_status} | {'yes' if r.canonical_source else 'no'} | {r.fixture_filename} | {r.reconciliation_status} |")
    (ROOT/"docs/research/RCE_Benchmark_Corpus_Inventory.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    special=lambda key:[f"{d['benchmark']['benchmark_id']}: {s.get('ticker') or s.get('company_name')}" for d in fixtures for s in d["securities"] if s["expectation"]==key]
    rec=["# RCE Benchmark Corpus Reconciliation v0.2","",f"The corpus contains exactly **{counts['benchmarks']}** source-reconciled benchmark fixtures: 12 reconciled foundation fixtures and 5 new fixtures.","",
         "## Source reconciliation","",f"- PDFs discovered: {len(records)}",f"- Canonical sources: {sum(r.canonical_source for r in records)}",f"- Exact duplicates: {sum(d['status']=='exact' for d in duplicates)}",f"- Near-duplicates: {sum(d['status']=='near-duplicate' for d in duplicates)}","- Canonical selection: every unique mapped PDF is canonical for its inferred domain.","",
         "## Counts","",f"- Benchmarks: {counts['benchmarks']}",f"- Categories: {counts['categories']}",f"- Securities/references: {counts['securities_and_references']}",f"- Sources: {counts['sources']}","- By benchmark:"]
    rec += [f"  - {d['benchmark']['benchmark_id']}: {len(d['categories'])} categories; {len(d['securities'])} securities/references" for d in fixtures]
    for title,key in [("Private references","private_reference"),("International references","international_reference"),("Fund references","fund_reference"),("Must-exclude records","must_exclude")]: rec += ["",f"## {title}",""]+[f"- {x}" for x in special(key)]
    rec += ["","## Unresolved provenance and classifications",""] + ([f"- {x['benchmark_id']}: {x['company_name']} - {x['issue']}" for x in unresolved] or ["- None."])
    rec += ["","## Cross-domain overlaps","","- American Express (AXP): Traditional Banking and Fintech","- Capital One (COF): Traditional Banking and identified by the Fintech/Banking boundary","- Robinhood (HOOD): Fintech and Crypto","- PayPal (PYPL): Fintech and Crypto","","The full PDF inventory and canonical source mapping are in `RCE_Benchmark_Corpus_Inventory.md`; machine-readable details are in `data/research/rce_benchmark_reconciliation_v0.2.json`."]
    (ROOT/"docs/research/RCE_Benchmark_Corpus_Reconciliation_v0.2.md").write_text("\n".join(rec)+"\n",encoding="utf-8")


def main():
    records, duplicates=inventory_pdfs(PDF_DIR); reconcile_existing(records); add_new(records); reports(records,duplicates)


if __name__ == "__main__": main()
