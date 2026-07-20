"""Build the versioned, read-only authored RCE source-corpus artifact.

This is an offline reconciliation utility.  The Explorer never parses PDFs at
runtime.  The audited company manifest is deliberately explicit: extraction
must reconcile every expected primary company and every known repeated table
placement or the build fails.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "docs/research/benchmarks"
OUTPUT = ROOT / "data/research/rce_authored_source_corpus_v0.1.json"
CORPUS_VERSION = "authored-source-v0.1"

SOURCE_META = {
    "ai-data-center-networking-cabling": ("AI Data Center Networking & Cabling", "datacenter networking companies.pdf"),
    "ai-power-supply-chain": ("AI Power Supply Chain", "ai power supply chain.pdf"),
    "crispr-ai-oncology": ("CRISPR & AI Oncology", "crispr ai oncology companies.pdf"),
    "critical-infrastructure-cybersecurity": ("Critical Infrastructure Cybersecurity", "critical infra cybersecurity companies.pdf"),
    "critical-minerals": ("Critical Minerals", "critical minerals companies.pdf"),
    "crypto-adjacent-companies": ("Crypto-Adjacent Companies", "crypto adjacent companies.pdf"),
    "defense-drones-counter-drone": ("Defense Drones & Counter-Drone", "defense drone companies.pdf"),
    "ev-autonomous-driving": ("EV & Autonomous Driving", "ev autonomous driving companies.pdf"),
    "fintech": ("Fintech", "fintech companies.pdf"),
    "fusion-energy": ("Fusion Energy", "fusion energy companies.pdf"),
    "glp1-obesity-drug-supply-chain": ("GLP-1 / Obesity Drug Supply Chain", "glp1 supply chain companies.pdf"),
    "nuclear-power-ai-data-centers": ("Nuclear Power for AI Data Centers", "nuclear data center companies.pdf"),
    "retail-sector": ("Retail Sector", "retail sector companies.pdf"),
    "robotics-humanoids": ("Robotics & Humanoids", "robotics humanoid companies.pdf"),
    "semiconductor-packaging": ("Semiconductor Packaging", "semiconductor packaging companies.pdf"),
    "space-exploration": ("Space Exploration", "space exploration companies.pdf"),
    "traditional-banking": ("Traditional Banking", "traditional banking companies.pdf"),
}

# Unique primary company-table constituents established by the integrity audit.
SOURCE_COMPANIES = {
    "ai-data-center-networking-cabling": ["Arista Networks", "Cisco Systems", "Nokia", "Broadcom", "Marvell Technology", "Coherent Corp", "Lumentum Holdings", "Credo Technology", "Astera Labs", "Fabrinet", "Ciena", "Amphenol", "TE Connectivity", "Corning", "CommScope", "Belden", "Lumen Technologies"],
    "ai-power-supply-chain": ["GE Vernova", "Siemens Energy", "Mitsubishi Heavy Industries", "Constellation Energy", "Vistra", "Oklo", "X-Energy", "NuScale Power", "Talen Energy", "Dominion Energy", "NextEra Energy", "Southern Company", "Duke Energy", "American Electric Power", "Entergy", "First Solar", "Brookfield Renewable", "Nextpower", "Orsted", "Fluence Energy", "Eos Energy Enterprises", "Albemarle", "Bloom Energy", "Plug Power", "Caterpillar", "Cummins", "Generac", "Eaton", "Vertiv", "Schneider Electric", "ABB", "Hitachi Energy", "Powell Industries", "Prysmian", "Quanta Services", "MasTec", "Kinder Morgan", "Williams Companies", "Energy Transfer"],
    "crispr-ai-oncology": ["CRISPR Therapeutics", "Intellia Therapeutics", "Beam Therapeutics", "Editas Medicine", "Caribou Biosciences", "Prime Medicine", "Recursion Pharmaceuticals", "Schrodinger", "Relay Therapeutics", "Insilico Medicine", "XtalPi", "Generate:Biomedicines", "Legend Biotech", "Autolus Therapeutics", "Allogene Therapeutics", "Fate Therapeutics", "Illumina", "10x Genomics", "Twist Bioscience", "Pacific Biosciences", "Thermo Fisher Scientific", "Eli Lilly", "Novartis", "Roche / Genentech", "Johnson & Johnson", "Bristol Myers Squibb", "GSK", "Gilead Sciences", "Merck"],
    "critical-infrastructure-cybersecurity": ["Palo Alto Networks", "Fortinet", "Cisco Systems", "Honeywell", "Motorola Solutions", "Rockwell Automation", "General Dynamics", "CrowdStrike", "Zscaler", "SentinelOne", "Check Point Software", "Okta", "Netscout Systems", "Qualys", "Tenable Holdings", "Akamai Technologies", "Varonis Systems", "Broadcom", "IBM"],
    "critical-minerals": ["MP Materials", "USA Rare Earth", "Lynas Rare Earths", "Ucore Rare Metals", "Freeport-McMoRan", "Southern Copper", "Ivanhoe Mines", "Teck Resources", "Rio Tinto", "Hudbay Minerals", "Almonty Industries", "United States Antimony Corp", "Perpetua Resources", "Sunshine Silver Mining & Refining"],
    "crypto-adjacent-companies": ["IREN", "MARA Holdings", "Riot Platforms", "CleanSpark", "TeraWulf", "Core Scientific", "Cipher Mining", "Bitdeer Technologies", "Hut 8", "HIVE Digital Technologies", "Canaan", "Coinbase Global", "Bullish", "Gemini", "Robinhood", "Circle Internet Group", "BitGo Holdings", "Galaxy Digital", "Bakkt", "Strategy (formerly MicroStrategy)", "Twenty One Capital", "PayPal", "Block (formerly Square)", "Visa", "CME Group"],
    "defense-drones-counter-drone": ["Lockheed Martin", "RTX", "Northrop Grumman", "L3Harris Technologies", "General Dynamics", "AeroVironment", "Kratos Defense & Security Solutions", "Red Cat Holdings", "Ondas Holdings", "Draganfly", "Unusual Machines", "AIRO Group Holdings", "ZenaTech", "Duke Robotics", "VisionWave Holdings", "DroneShield", "Axon Enterprise", "ParaZero Technologies", "Palantir Technologies"],
    "ev-autonomous-driving": ["Tesla", "BYD", "Rivian", "Lucid Group", "XPeng", "NIO", "Li Auto", "General Motors", "Ford", "Volkswagen Group", "Stellantis", "Toyota", "Alphabet (Waymo)", "Mobileye Global", "Pony.ai", "Aurora Innovation", "Hesai Group", "Innoviz Technologies", "Luminar Technologies", "Ouster", "Aeva Technologies", "Nvidia", "Qualcomm", "Ambarella", "ChargePoint", "EVgo", "Blink Charging", "Wallbox", "QuantumScape", "Solid Power", "Albemarle", "Panasonic", "Aptiv", "BorgWarner", "ON Semiconductor", "STMicroelectronics", "Uber Technologies", "Lyft"],
    "fintech": ["Visa", "Mastercard", "American Express", "Fiserv", "Global Payments", "FIS", "PayPal", "Block (formerly Square)", "Marqeta", "Chime Financial", "SoFi Technologies", "Nu Holdings (Nubank)", "Affirm Holdings", "Klarna Group", "Robinhood", "Interactive Brokers"],
    "fusion-energy": ["General Fusion Group", "TAE Technologies (via Trump Media)", "American Superconductor", "Bruker Corporation", "Linde plc", "Alphabet", "Eni", "Microsoft", "Chevron", "Cenovus Energy"],
    "glp1-obesity-drug-supply-chain": ["Novo Nordisk", "Eli Lilly", "Pfizer", "Amgen", "Viking Therapeutics", "Structure Therapeutics", "Lonza Group", "Samsung Biologics", "West Pharmaceutical Services", "Stevanato Group", "Gerresheimer", "Hims & Hers Health"],
    "nuclear-power-ai-data-centers": ["Constellation Energy", "Talen Energy", "Dominion Energy", "Vistra", "Oklo", "X-Energy", "NuScale Power", "GE Vernova", "Cameco", "Uranium Energy Corp", "NANO Nuclear Energy"],
    "retail-sector": ["Walmart", "Costco Wholesale", "Target", "BJ's Wholesale Club", "Home Depot", "Lowe's", "TJX Companies", "Ross Stores", "Burlington Stores", "Dillard's", "Macy's", "Kohl's", "Dollar General", "Dollar Tree", "Ralph Lauren", "Gap Inc.", "Abercrombie & Fitch", "American Eagle Outfitters", "Urban Outfitters", "Dick's Sporting Goods", "Academy Sports + Outdoors", "Best Buy", "Ulta Beauty", "Chewy", "Williams-Sonoma", "RH (Restoration Hardware)", "CVS Health", "Saks Global", "QVC Group", "Sportsman's Warehouse", "Leslie's"],
    "robotics-humanoids": ["Nidec", "Nabtesco", "Harmonic Drive Systems", "Moog", "ROBOTIS", "Inovance Technology", "Tuopu Group", "Zhejiang Sanhua Intelligent Controls", "Sensata Technologies", "TE Connectivity", "Nvidia", "Qualcomm", "Intel", "AMD", "Mobileye", "Alphabet", "Tesla", "UBTECH Robotics", "Hyundai Motor", "Xiaomi", "Faraday Future", "Richtech Robotics", "ABB", "FANUC", "Yaskawa Electric", "Teradyne", "Rockwell Automation", "Symbotic"],
    "semiconductor-packaging": ["TSMC", "Samsung Electronics", "Intel", "ASE Technology Holding", "Amkor Technology", "JCET Group", "Powertech Technology", "Tongfu Microelectronics", "ChipMOS Technologies", "BE Semiconductor Industries (Besi)", "ASMPT", "Kulicke & Soffa", "Applied Materials", "DISCO Corporation", "TOWA Corporation", "Teradyne", "Advantest", "Cohu", "Ibiden", "Shinko Electric Industries", "Unimicron", "Samsung Electro-Mechanics", "SK Hynix", "Micron Technology"],
    "space-exploration": ["SpaceX", "Rocket Lab", "Firefly Aerospace", "MDA Space", "Iridium Communications", "Globalstar", "AST SpaceMobile", "Viasat", "EchoStar", "Planet Labs", "BlackSky", "Spire Global", "Satellogic", "Redwire", "Karman Holdings", "Mercury Systems", "Intuitive Machines", "Voyager Technologies", "Virgin Galactic", "Lockheed Martin", "Northrop Grumman", "L3Harris Technologies", "RTX", "Wistron NeWeb", "T-Mobile US", "Verizon", "Kratos Defense"],
    "traditional-banking": ["JPMorgan Chase", "Bank of America", "Citigroup", "Wells Fargo", "Goldman Sachs", "Morgan Stanley", "US Bancorp", "PNC Financial Services", "Truist Financial", "Fifth Third Bancorp", "Citizens Financial Group", "Regions Financial", "M&T Bank", "State Street", "Bank of New York Mellon", "Northern Trust", "Capital One Financial", "American Express"],
}

EXPECTED_PLACEMENTS = {
    "ai-power-supply-chain": 41,
    "retail-sector": 32,
    "semiconductor-packaging": 25,
}

SPECIAL_GROUP_TICKERS = {
    "Oklo": "OKLO", "X-Energy": "XE", "NuScale Power": "SMR",
    "Talen Energy": "TLN", "Dominion Energy": "D",
}
GROUPED_COMPANIES = frozenset(SPECIAL_GROUP_TICKERS)

TICKER_OVERRIDES = {
    "Lumen Technologies": "LUMN", "Hitachi Energy": "TYO:6501",
    "Insilico Medicine": "HKEX-listed 2025", "Cisco Systems": "CSCO",
    "Sunshine Silver Mining & Refining": "recent S-1/IPO filer",
    "Twenty One Capital": "XXI", "Aurora Innovation": "AUR",
    "Panasonic": "OTC:PCRFY", "TAE Technologies (via Trump Media)": "DJT",
    "Bruker Corporation": "BRKR", "Samsung Biologics": "KRX:207940",
    "Gerresheimer": "XTRA:GXI", "Hims & Hers Health": "HIMS",
    "Block (formerly Square)": "XYZ", "Marqeta": "MQ",
    "CVS Health": "CVS", "Saks Global": "private (post-HBC)",
    "QVC Group": "QVCGA (pre-filing)", "EchoStar": "SATS / ECHO",
    "Mercury Systems": "MRCY", "Voyager Technologies": "VOYG",
    "M&T Bank": "MTB",
}

MATCH_ALIASES = {
    "NuScale Power": "NuScale",
    "Talen Energy": "Talen",
    "Dominion Energy": "Dominion",
    "Generate:Biomedicines": "Generate:Biomedicin es",
    "General Dynamics": "eneral Dynamics",
    "TAE Technologies (via Trump Media)": "TAE Technologies (via Trump Media)",
}

SUPPLEMENTAL_RECORDS = {
    "critical-infrastructure-cybersecurity": [
        ("Dragos", None, "private-company reference", "1", "OT/ICS & Industrial Cybersecurity"),
        ("Claroty", None, "private-company reference", "1", "OT/ICS & Industrial Cybersecurity"),
    ],
    "defense-drones-counter-drone": [
        ("Anduril Industries", None, "private-company reference", "3", "Notable Private Companies Shaping the Category"),
        ("Shield AI", None, "private-company reference", "3", "Notable Private Companies Shaping the Category"),
        ("Skydio", None, "private-company reference", "3", "Notable Private Companies Shaping the Category"),
        ("Epirus", None, "private-company reference", "3", "Notable Private Companies Shaping the Category"),
    ],
    "fintech": [
        ("Stripe", None, "private-company reference", "3", "Private Fintechs Worth Watching"),
        ("Revolut", None, "private-company reference", "3", "Private Fintechs Worth Watching"),
        ("Plaid", None, "private-company reference", "3", "Private Fintechs Worth Watching"),
        ("Brex", None, "private-company reference", "3", "Private Fintechs Worth Watching"),
        ("Ramp", None, "private-company reference", "3", "Private Fintechs Worth Watching"),
        ("Gusto", None, "private-company reference", "3", "Private Fintechs Worth Watching"),
    ],
    "fusion-energy": [
        ("Commonwealth Fusion Systems", None, "private-company reference", "2", "Private Companies Still Defining the Sector"),
        ("Helion Energy", None, "private-company reference", "2", "Private Companies Still Defining the Sector"),
    ],
    "glp1-obesity-drug-supply-chain": [
        ("CordenPharma", None, "private-company reference", "2", "Peptide Manufacturing & CDMOs"),
        ("Catalent", "CTLT", "prose-only reference", "2", "Delivery Devices, Packaging & Fill-Finish"),
        ("Ro", None, "private-company reference", "2", "Telehealth & Direct-to-Consumer Distribution"),
    ],
    "retail-sector": [
        ("Saks Global", None, "distressed/boundary case", "3", "Distressed / Bankruptcy Watch (2026)"),
        ("QVC Group", "QVCGA", "distressed/boundary case", "3", "Distressed / Bankruptcy Watch (2026)"),
        ("Kohl's", "KSS", "distressed/boundary case", "3", "Distressed / Bankruptcy Watch (2026)"),
        ("Sportsman's Warehouse", "SPWH", "distressed/boundary case", "3", "Distressed / Bankruptcy Watch (2026)"),
        ("Leslie's", "LESL", "distressed/boundary case", "4", "Distressed / Bankruptcy Watch (2026)"),
        ("Amazon", "AMZN", "categories-worth-adding example", "4", "Online/E-commerce Pure-Plays"),
        ("Etsy", "ETSY", "categories-worth-adding example", "4", "Online/E-commerce Pure-Plays"),
        ("Kroger", "KR", "categories-worth-adding example", "4", "Grocery/Supermarket"),
        ("Albertsons", "ACI", "categories-worth-adding example", "4", "Grocery/Supermarket"),
    ],
    "space-exploration": [
        ("ARK Space Exploration & Innovation ETF", "ARKX", "fund or ETF", "4", "Space-Adjacent ETFs"),
        ("Procure Space ETF", "UFO", "fund or ETF", "4", "Space-Adjacent ETFs"),
    ],
    "traditional-banking": [
        ("SPDR S&P Regional Banking ETF", "KRE", "fund or ETF", "2", "Regional & Super-Regional Banks"),
        ("BlackRock", "BLK", "categories-worth-adding example", "3", "Asset Managers"),
        ("Blackstone", "BX", "categories-worth-adding example", "3", "Asset Managers"),
    ],
}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _table_blocks(path: Path) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    section = "Uncategorized"
    columns: tuple[int, int, int] | None = None
    in_table = False
    for page_number, page in enumerate(PdfReader(path).pages, 1):
        pending: list[str] = []
        for line in page.extract_text(extraction_mode="layout").splitlines() + [""]:
            stripped = line.strip()
            heading = re.match(r"^(\d+)\.\s+(.+)$", stripped)
            if heading:
                section = heading.group(2).strip()
                in_table = False
            if stripped.startswith(("Categories Worth", "Category Worth", "Private Companies", "Notable Private", "Generated ")):
                in_table = False
                pending = []
            if "Company" in line and "Ticker" in line:
                company_index = line.index("Company")
                ticker_index = line.index("Ticker")
                role_index = line.find("Role", ticker_index)
                if role_index < 0:
                    role_index = line.find("Recent", ticker_index)
                columns = (company_index, ticker_index, role_index if role_index > ticker_index else ticker_index + 14)
                in_table = True
                pending = []
                continue
            if not stripped:
                if pending and in_table and columns:
                    ci, ti, ri = columns
                    company_text = " ".join(row[ci:ti].strip() for row in pending if len(row) > ci and row[ci:ti].strip())
                    ticker_text = "".join(row[ti:ri].strip() for row in pending if len(row) > ti and row[ti:ri].strip()).replace(" ", "")
                    blocks.append({"company_text": company_text, "ticker": ticker_text, "section": section, "page": str(page_number)})
                pending = []
            elif in_table:
                pending.append(line)
    return blocks


def _primary_records(benchmark_id: str, pdf_path: Path) -> list[dict[str, Any]]:
    expected = SOURCE_COMPANIES[benchmark_id]
    blocks = _table_blocks(pdf_path)
    records: list[dict[str, Any]] = []
    for block in blocks:
        company_key = _key(block["company_text"])
        matches = []
        for name in expected:
            match_keys = {_key(name), _key(MATCH_ALIASES.get(name, name))}
            if any(
                (len(match_key) <= 3 and match_key == company_key)
                or (len(match_key) > 3 and company_key.startswith(match_key))
                or (name in GROUPED_COMPANIES and match_key in company_key)
                for match_key in match_keys
            ):
                matches.append(name)
        for name in matches:
            ticker = TICKER_OVERRIDES.get(name, SPECIAL_GROUP_TICKERS.get(name, block["ticker"] or None))
            source_section = block["section"]
            if benchmark_id == "nuclear-power-ai-data-centers":
                source_section = (
                    "Companies With Signed Hyperscaler Deals"
                    if name in SOURCE_COMPANIES[benchmark_id][:6]
                    else "Public SMR / Nuclear Plays Without a Hyperscaler Deal Yet"
                )
            records.append({
                "company_name": name,
                "ticker_or_identifier": ticker,
                "source_page": block["page"],
                "source_section": source_section,
                "record_type": "primary company-table constituent",
                "source_notes": "Explicit company-table constituent in the authored source document.",
            })
    found = {_key(row["company_name"]) for row in records}
    missing = [name for name in expected if _key(name) not in found]
    if missing:
        raise RuntimeError(f"{benchmark_id}: primary source extraction missed {missing}")
    expected_count = EXPECTED_PLACEMENTS.get(benchmark_id, len(expected))
    if len(records) != expected_count:
        raise RuntimeError(f"{benchmark_id}: expected {expected_count} placements, extracted {len(records)}")
    counts: dict[str, int] = {}
    for row in records:
        key = _key(row["company_name"])
        counts[key] = counts.get(key, 0) + 1
    placement: dict[str, int] = {}
    for row in records:
        key = _key(row["company_name"])
        placement[key] = placement.get(key, 0) + 1
        row["duplicate_placement"] = counts[key] > 1
        row["placement_index"] = placement[key]
    return records


def build() -> dict[str, Any]:
    benchmarks = []
    for benchmark_id, (benchmark_name, source_document) in SOURCE_META.items():
        pdf_path = PDF_DIR / source_document
        primary = _primary_records(benchmark_id, pdf_path)
        supplemental = [{
            "company_name": company,
            "ticker_or_identifier": ticker,
            "source_page": page,
            "source_section": section,
            "record_type": record_type,
            "source_notes": "Explicit non-primary reference preserved for filtering and future review.",
            "duplicate_placement": False,
            "placement_index": 1,
        } for company, ticker, record_type, page, section in SUPPLEMENTAL_RECORDS.get(benchmark_id, [])]
        benchmarks.append({
            "benchmark_id": benchmark_id,
            "benchmark_name": benchmark_name,
            "source_corpus_version": CORPUS_VERSION,
            "source_document": source_document,
            "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "primary_unique_company_count": len({_key(row["company_name"]) for row in primary}),
            "primary_placement_count": len(primary),
            "records": primary + supplemental,
        })
    primary_records = [row for benchmark in benchmarks for row in benchmark["records"] if row["record_type"] == "primary company-table constituent"]
    unique_by_domain = sum(benchmark["primary_unique_company_count"] for benchmark in benchmarks)
    if len(benchmarks) != 17 or unique_by_domain != 377 or len(primary_records) != 381:
        raise RuntimeError(
            f"Corpus reconciliation failed: domains={len(benchmarks)}, unique={unique_by_domain}, placements={len(primary_records)}"
        )
    return {
        "schema_version": "1.0",
        "source_corpus_version": CORPUS_VERSION,
        "generated_from": "docs/research/benchmarks",
        "benchmark_count": len(benchmarks),
        "primary_unique_company_count": unique_by_domain,
        "primary_placement_count": len(primary_records),
        "benchmarks": benchmarks,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
