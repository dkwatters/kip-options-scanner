"""Source inventory helpers for the versioned RCE benchmark corpus."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

from pypdf import PdfReader


DOMAIN_BY_FILENAME = {
    "ai power supply chain.pdf": ("AI Power Supply Chain", "ai-power-supply-chain.json"),
    "crispr ai oncology companies.pdf": ("CRISPR & AI Oncology", "crispr-ai-oncology.json"),
    "critical infra cybersecurity companies.pdf": ("Critical Infrastructure Cybersecurity", "critical-infrastructure-cybersecurity.json"),
    "critical minerals companies.pdf": ("Critical Minerals", "critical-minerals.json"),
    "crypto adjacent companies.pdf": ("Crypto-Adjacent Companies", "crypto-adjacent-companies.json"),
    "datacenter networking companies.pdf": ("AI Data Center Networking & Cabling", "ai-data-center-networking-cabling.json"),
    "defense drone companies.pdf": ("Defense Drones & Counter-Drone", "defense-drones-counter-drone.json"),
    "ev autonomous driving companies.pdf": ("EV & Autonomous Driving", "ev-autonomous-driving.json"),
    "fintech companies.pdf": ("Fintech", "fintech.json"),
    "fusion energy companies.pdf": ("Fusion Energy", "fusion-energy.json"),
    "glp1 supply chain companies.pdf": ("GLP-1 / Obesity Drug Supply Chain", "glp1-obesity-drug-supply-chain.json"),
    "nuclear data center companies.pdf": ("Nuclear Power for AI Data Centers", "nuclear-power-ai-data-centers.json"),
    "retail sector companies.pdf": ("Retail Sector", "retail-sector.json"),
    "robotics humanoid companies.pdf": ("Robotics & Humanoids", "robotics-humanoids.json"),
    "semiconductor packaging companies.pdf": ("Semiconductor Packaging", "semiconductor-packaging.json"),
    "space exploration companies.pdf": ("Space Exploration", "space-exploration.json"),
    "traditional banking companies.pdf": ("Traditional Banking", "traditional-banking.json"),
}


@dataclass(frozen=True)
class PDFInventoryRecord:
    filename: str
    domain: str
    page_count: int
    file_size: int
    sha256: str
    duplicate_status: str
    canonical_source: bool
    fixture_filename: str
    reconciliation_status: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalized_text(reader: PdfReader) -> str:
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\W+", " ", text).casefold().strip()


def inventory_pdfs(directory: Path | str) -> tuple[list[PDFInventoryRecord], list[dict[str, object]]]:
    """Inventory PDFs and detect exact or high-similarity content duplicates."""
    paths = sorted(Path(directory).glob("*.pdf"))
    details = []
    for path in paths:
        raw = path.read_bytes()
        reader = PdfReader(path)
        details.append((path, len(reader.pages), len(raw), hashlib.sha256(raw).hexdigest(), _normalized_text(reader)))
    duplicate_of: dict[str, tuple[str, str, float]] = {}
    duplicates: list[dict[str, object]] = []
    for index, left in enumerate(details):
        for right in details[index + 1:]:
            kind = None
            ratio = 1.0 if left[3] == right[3] else SequenceMatcher(None, left[4], right[4]).ratio()
            if left[3] == right[3]:
                kind = "exact"
            elif ratio >= 0.92:
                kind = "near-duplicate"
            if kind:
                duplicate_of[right[0].name] = (left[0].name, kind, ratio)
                duplicates.append({"filename": right[0].name, "canonical_filename": left[0].name, "status": kind, "similarity": round(ratio, 4)})
    records = []
    for path, pages, size, digest, _ in details:
        domain, fixture = DOMAIN_BY_FILENAME.get(path.name, ("Unmapped - human review required", "unmapped"))
        duplicate = duplicate_of.get(path.name)
        records.append(PDFInventoryRecord(
            path.name, domain, pages, size, digest,
            f"{duplicate[1]} of {duplicate[0]}" if duplicate else "unique",
            duplicate is None, fixture,
            "reconciled" if path.name in DOMAIN_BY_FILENAME else "human_review_required",
        ))
    return records, duplicates


def source_page_for_company(pdf_path: Path, company_name: str) -> str | None:
    """Return the first 1-based source page containing a company name."""
    needle = re.sub(r"\W+", "", company_name).casefold()
    for number, page in enumerate(PdfReader(pdf_path).pages, 1):
        haystack = re.sub(r"\W+", "", page.extract_text() or "").casefold()
        if needle and needle in haystack:
            return str(number)
    return None
