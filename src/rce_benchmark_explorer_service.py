"""Immutable read models for the certified RCE benchmark baseline."""
from __future__ import annotations

import json
import logging
import re
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

LOGGER = logging.getLogger(__name__)

DEFAULT_RUN_LABEL = "baseline-v0.1-providerfix"
DEFAULT_BASELINE_PATH = Path("data/research/rce_benchmark_baseline_v0.1.1.json")
DEFAULT_FIXTURE_DIR = Path("tests/fixtures/rce_benchmarks")
DEFAULT_SCORING_CONFIG_PATH = Path("config/rce_benchmark_scoring_v0.1.json")
DEFAULT_DATABASE_PATH = Path("data/research/rce_benchmarks.sqlite")
DEFAULT_SOURCE_CORPUS_PATH = Path("data/research/rce_authored_source_corpus_v0.1.json")
DEFAULT_CURATOR_APPROVAL_PATH = Path("data/research/rce_benchmark_curator_approvals_v0.1.json")

UNEXPECTED_EXPLANATION = (
    "Unexpected candidate means the RCE returned the security, but it is not currently "
    "present in the evaluation fixture. It requires review and is not automatically incorrect."
)
CERTIFIED_REVIEW_STATE_LABEL = "Certified-snapshot human review state"
COMPLETENESS_LIMITATION = (
    "The certified evaluator may record completeness indicators without retaining the full "
    "candidate-level rationale or evidence narrative in the comparison result."
)
METRIC_LABELS = MappingProxyType({
    "must_include_recall": "Must include recall",
    "weighted_candidate_recall": "Weighted candidate recall",
    "must_exclude_compliance": "Must-exclude compliance",
    "category_coverage": "Category coverage",
    "listing_constraint_compliance": "Listing constraint compliance",
    "candidate_validity": "Candidate validity",
    "rationale_completeness": "Rationale completeness",
    "evidence_completeness": "Evidence completeness",
    "ranking_quality": "Ranking quality",
    "schema_provider_integrity": "Schema and provider integrity",
})
METRIC_EXPLANATIONS = MappingProxyType({
    "must_include_recall": "Share of reviewed must-include securities returned.",
    "weighted_candidate_recall": "Recall across expected candidates using configured classification weights.",
    "must_exclude_compliance": "Compliance with explicit must-exclude expectations after configured penalties.",
    "category_coverage": "Weighted exact coverage of reviewed categories, including excluded-category penalties.",
    "listing_constraint_compliance": "Compliance with deterministically observable listing and entity constraints.",
    "candidate_validity": "Share of returned candidates that match reviewed public-security references and pass validation.",
    "rationale_completeness": "Share of returned candidates with the rationale fields required by the evaluator.",
    "evidence_completeness": "Share of returned candidates with structured evidence when the artifact supports it.",
    "ranking_quality": "Discounted rank credit for must-include and should-include securities.",
    "schema_provider_integrity": "Whether schema and provider verification succeeded without fallback use.",
})


@dataclass(frozen=True, slots=True)
class MetricExplanation:
    metric_name: str
    display_name: str
    raw_value: float
    configured_weight: float
    weighted_contribution: float
    calculation_note: str
    plain_language_explanation: str


@dataclass(frozen=True, slots=True)
class CandidateComparison:
    ticker: str | None
    company_name: str
    expected_classification: str | None
    returned: bool
    returned_rank: int | None
    expected_category: str | None
    returned_category: str | None
    category_match: bool
    listing_valid: bool
    public_status_valid: bool
    validation_status: str
    comparison_outcome: str
    rationale_present: bool
    evidence_present: bool
    reviewer_status: str | None
    reviewer_notes: str | None
    score_consequence: str


@dataclass(frozen=True, slots=True)
class CategoryComparison:
    category_name: str
    expected_status: str
    importance: float
    returned: bool
    coverage_credit: float
    notes: str | None


@dataclass(frozen=True, slots=True)
class DomainSummary:
    benchmark_id: str
    benchmark_name: str
    question: str
    overall_score: float | None
    execution_status: str
    benchmark_version: str
    run_label: str
    unresolved_unexpected_candidates: int


@dataclass(frozen=True, slots=True)
class ReviewedBenchmark:
    description: str | None
    review_notes: str | None
    reviewed_by: str | None
    source_document: str | None
    source_date: str | None
    expected_categories: tuple[Mapping[str, Any], ...]
    constituents: tuple[Mapping[str, Any], ...]
    expected_candidates: tuple[Mapping[str, Any], ...]
    exclusions: tuple[Mapping[str, Any], ...]
    caveats: tuple[str, ...]
    sources: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ReviewedCorpus:
    """Complete evaluation-fixture corpus, independent of run results."""

    benchmark_count: int
    category_count: int
    constituent_count: int
    categories: tuple[Mapping[str, Any], ...]
    constituents: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AuthoredSourceCandidate:
    benchmark_id: str
    benchmark_name: str
    source_corpus_version: str
    source_document: str
    source_page: str
    source_section: str
    company_name: str
    ticker_or_identifier: str | None
    record_type: str
    source_notes: str | None
    duplicate_placement: bool
    placement_index: int


@dataclass(frozen=True, slots=True)
class RCECorpusCandidate:
    company_name: str
    ticker: str | None
    returned_rank: int | None
    returned_category: str | None
    validation_status: str
    rationale_present: bool
    evidence_present: bool


@dataclass(frozen=True, slots=True)
class CorpusComparisonRow:
    company_name: str
    ticker_or_identifier: str | None
    appears_in_authored_corpus: bool
    appears_in_rce_corpus: bool
    authored_category: str | None
    rce_category: str | None
    category_match: bool | None
    rce_rank: int | None
    normalized_matching_key: str
    comparison_outcome: str
    source_pages: tuple[str, ...]
    validation_status: str | None
    rationale_present: bool | None
    evidence_present: bool | None
    explanation: str


@dataclass(frozen=True, slots=True)
class CorpusComparisonSummary:
    benchmark_id: str
    source_corpus_version: str | None
    source_document: str | None
    authored_unique_count: int
    authored_placement_count: int
    rce_candidate_count: int
    agreement_count: int
    authored_only_count: int
    rce_only_count: int
    category_review_count: int
    identity_review_count: int
    authored_candidates: tuple[AuthoredSourceCandidate, ...]
    rce_candidates: tuple[RCECorpusCandidate, ...]
    rows: tuple[CorpusComparisonRow, ...]
    available: bool = True
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class SourceEvidenceSummary:
    source_section: str
    source_document: str
    source_page: str
    source_notes: str | None
    duplicate_placement: bool
    placement_index: int


@dataclass(frozen=True, slots=True)
class RCECandidateSummary:
    company_name: str
    ticker: str | None
    rank: int | None
    category_metadata: str | None
    validation_status: str
    rationale_present: bool
    evidence_present: bool
    benchmark_consequence: str


@dataclass(frozen=True, slots=True)
class ComparisonContext:
    company_name: str
    ticker_or_identifier: str | None
    comparison_status: str


@dataclass(frozen=True, slots=True)
class CompanyInvestigation:
    benchmark_id: str
    benchmark_name: str
    company_name: str
    ticker_or_identifier: str | None
    originating_side: str
    comparison_outcome: str
    comparison_status: str
    appears_in_authored_corpus: bool
    appears_in_rce_corpus: bool
    rce_rank: int | None
    matching_method: str
    explanation: str
    source_evidence: tuple[SourceEvidenceSummary, ...]
    rce_candidate: RCECandidateSummary | None
    comparison_context: tuple[ComparisonContext, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkOfRecordMember:
    benchmark_id: str
    company_name: str
    ticker_or_identifier: str | None
    inclusion_source: str
    comparison_outcome: str


@dataclass(frozen=True, slots=True)
class CuratorCorpusRow:
    """Presentation-neutral row state for the inline curator workflow."""

    matching_key: str
    company_name: str
    ticker: str | None
    rank: int | None
    comparison_outcome: str
    included: bool


@dataclass(frozen=True, slots=True)
class CuratorProgress:
    agreements_included: int
    curator_additions: int
    pending_authored_only: int
    pending_rce_discoveries: int
    total_members: int


class CuratorApprovalRepository:
    """Small dedicated store for idempotent curator inclusion decisions."""

    def __init__(self, path: Path | str = DEFAULT_CURATOR_APPROVAL_PATH) -> None:
        self._path = Path(path)

    def _read(self) -> list[dict[str, Any]]:
        if not self._path.is_file():
            return []
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Unable to read curator approvals: {error}") from error
        approvals = document.get("approvals", []) if isinstance(document, dict) else []
        return [dict(row) for row in approvals if isinstance(row, dict)]

    def approved_keys(self, benchmark_id: str) -> frozenset[str]:
        return frozenset(
            str(row.get("matching_key")) for row in self._read()
            if row.get("benchmark_id") == benchmark_id and row.get("matching_key")
        )

    def approve(self, benchmark_id: str, row: CorpusComparisonRow) -> bool:
        if row.comparison_outcome not in {"authored_only", "rce_only"}:
            raise ValueError("Only authored-only companies and RCE discoveries require curator approval.")
        approvals = self._read()
        if any(
            item.get("benchmark_id") == benchmark_id
            and item.get("matching_key") == row.normalized_matching_key
            for item in approvals
        ):
            return False
        approvals.append({
            "benchmark_id": benchmark_id,
            "matching_key": row.normalized_matching_key,
            "company_name": row.company_name,
            "ticker_or_identifier": row.ticker_or_identifier,
            "comparison_outcome": row.comparison_outcome,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        })
        self._path.parent.mkdir(parents=True, exist_ok=True)
        document = {"schema_version": "curator-approvals-v0.1", "approvals": approvals}
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self._path.parent, delete=False, suffix=".tmp",
        ) as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(self._path)
        return True


@dataclass(frozen=True, slots=True)
class BenchmarkDetail:
    benchmark_id: str
    benchmark_name: str
    benchmark_version: str
    question: str
    run_label: str
    provider: str
    model: str
    prompt_version: str
    scoring_configuration_version: str
    execution_status: str
    overall_score: float | None
    reviewed: ReviewedBenchmark | None
    candidates: tuple[CandidateComparison, ...]
    categories: tuple[CategoryComparison, ...]
    metrics: tuple[MetricExplanation, ...]
    parser_warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def candidates_in_group(self, group: str) -> tuple[CandidateComparison, ...]:
        return tuple(row for row in self.candidates if _group(row) == group)


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_label: str
    domain_count: int
    successful_domain_count: int
    domains: tuple[DomainSummary, ...]
    unresolved_review_count: int
    review_state_label: str = CERTIFIED_REVIEW_STATE_LABEL
    available: bool = True
    error_message: str | None = None


def _frozen(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(row))


def _identity_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _category_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _ticker_keys(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    keys = set()
    for part in re.split(r"[/,]", value.upper()):
        token = part.strip()
        if ":" in token:
            listing, symbol = token.rsplit(":", 1)
            listing = re.sub(r"[^A-Z0-9]", "", listing)
            symbol = re.sub(r"[^A-Z0-9.]", "", symbol)
            token = f"{listing}:{symbol}" if listing and symbol else symbol
        else:
            token = re.sub(r"[^A-Z0-9.]", "", token)
        if token and token not in {"PRIVATE", "RECENT", "FILER", "LISTED", "IPO"}:
            keys.add(token)
    return frozenset(keys)


def compare_corpora(
    authored: tuple[AuthoredSourceCandidate, ...],
    rce: tuple[RCECorpusCandidate, ...],
) -> tuple[CorpusComparisonRow, ...]:
    """Compare corpora using ticker/identifier first, then exact normalized names.

    Category labels remain metadata and never determine the primary outcome.
    Ticker/name conflicts and non-unique matches are surfaced for identity review;
    no fuzzy, probabilistic, or LLM identity matching is performed.
    """
    placements_by_name: dict[str, list[AuthoredSourceCandidate]] = {}
    for row in authored:
        placements_by_name.setdefault(_identity_name(row.company_name), []).append(row)
    authored_groups = tuple(placements_by_name.values())
    by_ticker: dict[str, set[int]] = {}
    for index, group in enumerate(authored_groups):
        for ticker in _ticker_keys(group[0].ticker_or_identifier):
            by_ticker.setdefault(ticker, set()).add(index)

    matched: set[int] = set()
    results: list[CorpusComparisonRow] = []
    for candidate in sorted(rce, key=lambda row: (row.returned_rank is None, row.returned_rank or 0, row.company_name.casefold())):
        name_key = _identity_name(candidate.company_name)
        name_hits = {index for index, group in enumerate(authored_groups) if _identity_name(group[0].company_name) == name_key}
        ticker_hits = set().union(*(by_ticker.get(key, set()) for key in _ticker_keys(candidate.ticker))) if candidate.ticker else set()
        candidate_tickers = _ticker_keys(candidate.ticker)
        conflict = bool(candidate_tickers and name_hits and ticker_hits != name_hits)
        hits = ticker_hits if candidate_tickers else name_hits
        if conflict or len(hits) > 1:
            outcome = "identity_review"
            explanation = "Deterministic ticker and name keys are ambiguous or point to different authored identities."
            authored_group = authored_groups[next(iter(hits))] if len(hits) == 1 else []
        elif len(hits) == 1:
            index = next(iter(hits))
            matched.add(index)
            authored_group = authored_groups[index]
            authored_categories = tuple(dict.fromkeys(row.source_section for row in authored_group))
            category_match = _category_key(candidate.returned_category) in {_category_key(value) for value in authored_categories}
            outcome = "agreement"
            method = "normalized ticker/identifier" if candidate_tickers else "unambiguous normalized company name fallback"
            explanation = f"Present in both corpora; matched by {method}."
            if not category_match:
                explanation += " Category labels differ and are retained only as secondary metadata."
            results.append(CorpusComparisonRow(
                authored_group[0].company_name, candidate.ticker or authored_group[0].ticker_or_identifier,
                True, True, " | ".join(authored_categories), candidate.returned_category,
                category_match, candidate.returned_rank,
                f"ticker:{sorted(_ticker_keys(candidate.ticker or authored_group[0].ticker_or_identifier))[0]}" if _ticker_keys(candidate.ticker or authored_group[0].ticker_or_identifier) else f"name:{name_key}",
                outcome, tuple(dict.fromkeys(row.source_page for row in authored_group)),
                candidate.validation_status, candidate.rationale_present, candidate.evidence_present, explanation,
            ))
            continue
        else:
            authored_group = []
            outcome = "rce_only"
            explanation = "RCE discovery not present in the authored source corpus."

        authored_categories = tuple(dict.fromkeys(row.source_section for row in authored_group))
        results.append(CorpusComparisonRow(
            authored_group[0].company_name if authored_group else candidate.company_name,
            candidate.ticker or (authored_group[0].ticker_or_identifier if authored_group else None),
            bool(authored_group), True, " | ".join(authored_categories) or None, candidate.returned_category,
            None, candidate.returned_rank,
            f"name:{name_key}", outcome,
            tuple(dict.fromkeys(row.source_page for row in authored_group)),
            candidate.validation_status, candidate.rationale_present, candidate.evidence_present, explanation,
        ))

    for index, group in enumerate(authored_groups):
        if index in matched:
            continue
        categories = tuple(dict.fromkeys(row.source_section for row in group))
        ticker_keys = sorted(_ticker_keys(group[0].ticker_or_identifier))
        results.append(CorpusComparisonRow(
            group[0].company_name, group[0].ticker_or_identifier, True, False,
            " | ".join(categories), None, None, None,
            f"ticker:{ticker_keys[0]}" if ticker_keys else f"name:{_identity_name(group[0].company_name)}",
            "authored_only", tuple(dict.fromkeys(row.source_page for row in group)),
            None, None, None, "Not returned in the stored RCE candidate corpus.",
        ))
    order = {"identity_review": 0, "authored_only": 1, "rce_only": 2, "agreement": 3}
    return tuple(sorted(results, key=lambda row: (order[row.comparison_outcome], row.company_name.casefold())))


def _group(row: CandidateComparison) -> str:
    if row.expected_classification == "must_exclude" and row.returned:
        return "must_exclude"
    return {
        "expected_returned": "expected_returned",
        "expected_missing": "expected_missing",
        "unexpected_candidate": "unexpected",
        "must_exclude_returned": "must_exclude",
    }.get(row.comparison_outcome, "other")


def _score_consequence(row: Mapping[str, Any]) -> str:
    outcome = row.get("comparison_outcome")
    classification = row.get("expected_classification")
    if classification == "must_exclude" and row.get("returned"):
        return "Must-exclude compliance penalty applies."
    if outcome == "expected_missing":
        return "Observed omission and benchmark consequence: recall credit was not earned; ranking credit may also be affected."
    if outcome == "expected_returned":
        return "Earns configured recall credit; rank, category, validity, rationale, and evidence are evaluated separately."
    if outcome == "unexpected_candidate":
        return "No expected-candidate recall credit; validity and completeness metrics still interpret the returned candidate."
    return "No candidate-level consequence recorded."


class RCEBenchmarkExplorerService:
    """Load certified JSON artifacts without exposing mutation operations.

    Sprint 1 deliberately reports review state from the certified baseline snapshot.
    ``database_path`` is retained for configuration compatibility but is never opened;
    the explorer must not imply that snapshot statuses are a live database queue.
    """

    def __init__(self, *, baseline_path: Path | str = DEFAULT_BASELINE_PATH,
                 fixture_dir: Path | str = DEFAULT_FIXTURE_DIR,
                 source_corpus_path: Path | str = DEFAULT_SOURCE_CORPUS_PATH,
                 scoring_config_path: Path | str = DEFAULT_SCORING_CONFIG_PATH,
                 database_path: Path | str = DEFAULT_DATABASE_PATH,
                 curator_approval_path: Path | str = DEFAULT_CURATOR_APPROVAL_PATH,
                 run_label: str = DEFAULT_RUN_LABEL) -> None:
        self._baseline_path = Path(baseline_path)
        self._fixture_dir = Path(fixture_dir)
        self._source_corpus_path = Path(source_corpus_path)
        self._scoring_config_path = Path(scoring_config_path)
        self._database_path = Path(database_path)  # Availability is optional; never opened for writing.
        self._curator_approvals = CuratorApprovalRepository(curator_approval_path)
        self._run_label = run_label
        self._error: str | None = None
        self._diagnostics: list[str] = []
        self._runs = self._load_runs()
        self._fixtures = self._load_fixtures()
        self._source_corpus = self._load_source_corpus()
        self._config = self._load_config()

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_runs(self) -> tuple[Mapping[str, Any], ...]:
        if not self._baseline_path.is_file():
            self._error = f"Certified baseline is missing: {self._baseline_path}"
            return ()
        try:
            document = self._read_json(self._baseline_path)
            if not isinstance(document, list):
                raise ValueError("certified baseline must contain a list")
            runs = tuple(row for row in document if isinstance(row, dict) and row.get("run_label") == self._run_label)
            if not runs:
                self._error = f"Certified run label is missing: {self._run_label}"
            return runs
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self._error = f"Unable to read certified baseline: {error}"
            return ()

    def _load_fixtures(self) -> Mapping[str, Mapping[str, Any]]:
        fixtures: dict[str, Mapping[str, Any]] = {}
        if self._fixture_dir.is_dir():
            for path in sorted(self._fixture_dir.glob("*.json")):
                try:
                    document = self._read_json(path)
                    key = document.get("benchmark", {}).get("benchmark_id")
                    if key:
                        fixtures[str(key)] = document
                except (OSError, ValueError, json.JSONDecodeError) as error:
                    message = f"Unable to read fixture {path}: {error}"
                    self._diagnostics.append(message)
                    LOGGER.warning(message)
                    continue
        else:
            self._diagnostics.append(f"Canonical fixture directory is missing: {self._fixture_dir}")
        return MappingProxyType(fixtures)

    def _load_config(self) -> Mapping[str, Any]:
        try:
            document = self._read_json(self._scoring_config_path)
            return MappingProxyType(document if isinstance(document, dict) else {})
        except (OSError, ValueError, json.JSONDecodeError) as error:
            message = f"Unable to read scoring configuration {self._scoring_config_path}: {error}"
            self._diagnostics.append(message)
            LOGGER.warning(message)
            return MappingProxyType({})

    def _load_source_corpus(self) -> Mapping[str, Mapping[str, Any]]:
        if not self._source_corpus_path.is_file():
            self._diagnostics.append(f"Authored source corpus is missing: {self._source_corpus_path}")
            return MappingProxyType({})
        try:
            document = self._read_json(self._source_corpus_path)
            benchmarks = document.get("benchmarks", []) if isinstance(document, dict) else []
            rows = {
                str(row["benchmark_id"]): row
                for row in benchmarks
                if isinstance(row, dict) and row.get("benchmark_id")
            }
            return MappingProxyType(rows)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            message = f"Unable to read authored source corpus {self._source_corpus_path}: {error}"
            self._diagnostics.append(message)
            LOGGER.warning(message)
            return MappingProxyType({})

    @property
    def diagnostics(self) -> tuple[str, ...]:
        """Non-fatal artifact diagnostics suitable for logs or a friendly UI notice."""
        return tuple(self._diagnostics)

    @staticmethod
    def _candidate(row: Mapping[str, Any]) -> CandidateComparison:
        return CandidateComparison(
            row.get("ticker"), str(row.get("company_name") or row.get("ticker") or "Unknown"),
            row.get("expected_classification"), bool(row.get("returned")), row.get("returned_rank"),
            row.get("expected_category"), row.get("returned_category"), bool(row.get("category_match")),
            bool(row.get("listing_valid")), bool(row.get("public_status_valid")),
            str(row.get("validation_status") or "unknown"), str(row.get("comparison_outcome") or "unknown"),
            bool(row.get("rationale_present")), bool(row.get("evidence_present")),
            row.get("reviewer_status"), row.get("reviewer_notes"), _score_consequence(row),
        )

    def list_domains(self) -> tuple[DomainSummary, ...]:
        domains = []
        for run in self._runs:
            candidates = tuple(self._candidate(row) for row in run.get("evaluation", {}).get("candidate_results", []))
            unresolved = sum(_group(row) == "unexpected" and row.reviewer_status in (None, "needs_verification") for row in candidates)
            domains.append(DomainSummary(
                str(run.get("benchmark_id", "")), str(run.get("benchmark_name", "")),
                str(run.get("benchmark_question", "")), run.get("overall_score"),
                str(run.get("run_status") or "unknown"), str(run.get("benchmark_version", "")),
                str(run.get("run_label", "")), unresolved,
            ))
        return tuple(sorted(domains, key=lambda row: row.benchmark_name.casefold()))

    def run_summary(self) -> RunSummary:
        domains = self.list_domains()
        return RunSummary(
            self._run_label, len(domains), sum(row.execution_status == "success" for row in domains),
            domains, sum(row.unresolved_unexpected_candidates for row in domains),
            CERTIFIED_REVIEW_STATE_LABEL, bool(self._runs), self._error,
        )

    def reviewed_corpus(self) -> ReviewedCorpus:
        """Return every reviewed category and constituent from canonical fixtures.

        Benchmark identifiers and names are added to each row so callers can render
        the complete corpus without joining it to the summarized run projection.
        """
        categories: list[Mapping[str, Any]] = []
        constituents: list[Mapping[str, Any]] = []
        for benchmark_id, fixture in self._fixtures.items():
            identity = fixture.get("benchmark", {})
            context = {
                "benchmark_id": benchmark_id,
                "benchmark_name": str(identity.get("benchmark_name") or benchmark_id),
                "benchmark_version": str(identity.get("version") or ""),
            }
            categories.extend(_frozen({**context, **row}) for row in fixture.get("categories", []))
            constituents.extend(_frozen({**context, **row}) for row in fixture.get("securities", []))
        return ReviewedCorpus(
            benchmark_count=len(self._fixtures),
            category_count=len(categories),
            constituent_count=len(constituents),
            categories=tuple(categories),
            constituents=tuple(constituents),
        )

    def authored_source_candidates(
        self, benchmark_id: str, *, primary_only: bool = True,
    ) -> tuple[AuthoredSourceCandidate, ...]:
        benchmark = self._source_corpus.get(benchmark_id)
        if not benchmark:
            return ()
        rows = []
        for row in benchmark.get("records", []):
            if primary_only and row.get("record_type") != "primary company-table constituent":
                continue
            rows.append(AuthoredSourceCandidate(
                benchmark_id=benchmark_id,
                benchmark_name=str(benchmark.get("benchmark_name") or benchmark_id),
                source_corpus_version=str(benchmark.get("source_corpus_version") or "unknown"),
                source_document=str(benchmark.get("source_document") or ""),
                source_page=str(row.get("source_page") or ""),
                source_section=str(row.get("source_section") or "Uncategorized"),
                company_name=str(row.get("company_name") or "Unknown"),
                ticker_or_identifier=row.get("ticker_or_identifier"),
                record_type=str(row.get("record_type") or "unknown"),
                source_notes=row.get("source_notes"),
                duplicate_placement=bool(row.get("duplicate_placement")),
                placement_index=int(row.get("placement_index") or 1),
            ))
        return tuple(rows)

    def rce_corpus_candidates(self, benchmark_id: str) -> tuple[RCECorpusCandidate, ...]:
        run = next((row for row in self._runs if row.get("benchmark_id") == benchmark_id), None)
        if run is None:
            return ()
        candidates = []
        for row in run.get("evaluation", {}).get("candidate_results", []):
            if not row.get("returned"):
                continue
            candidates.append(RCECorpusCandidate(
                company_name=str(row.get("company_name") or row.get("ticker") or "Unknown"),
                ticker=row.get("ticker"),
                returned_rank=row.get("returned_rank"),
                returned_category=row.get("returned_category"),
                validation_status=str(row.get("validation_status") or "unknown"),
                rationale_present=bool(row.get("rationale_present")),
                evidence_present=bool(row.get("evidence_present")),
            ))
        return tuple(sorted(candidates, key=lambda row: (row.returned_rank is None, row.returned_rank or 0)))

    def corpus_comparison(self, benchmark_id: str) -> CorpusComparisonSummary:
        source = self._source_corpus.get(benchmark_id)
        if not source:
            return CorpusComparisonSummary(
                benchmark_id, None, None, 0, 0, 0, 0, 0, 0, 0, 0, (), (), (),
                False, f"Authored source corpus is unavailable for {benchmark_id}.",
            )
        run = next((row for row in self._runs if row.get("benchmark_id") == benchmark_id), None)
        authored = self.authored_source_candidates(benchmark_id)
        if run is None:
            return CorpusComparisonSummary(
                benchmark_id, str(source.get("source_corpus_version") or "unknown"),
                str(source.get("source_document") or ""),
                int(source.get("primary_unique_company_count") or 0), len(authored), 0,
                0, 0, 0, 0, 0, authored, (), (), False,
                f"Stored RCE result is unavailable for {benchmark_id}.",
            )
        rce = self.rce_corpus_candidates(benchmark_id)
        rows = compare_corpora(authored, rce)
        counts = {name: sum(row.comparison_outcome == name for row in rows) for name in (
            "agreement", "authored_only", "rce_only", "identity_review"
        )}
        return CorpusComparisonSummary(
            benchmark_id, str(source.get("source_corpus_version") or "unknown"),
            str(source.get("source_document") or ""),
            int(source.get("primary_unique_company_count") or 0), len(authored), len(rce),
            counts["agreement"], counts["authored_only"], counts["rce_only"],
            0, counts["identity_review"], authored, rce, rows,
        )

    def company_investigation(
        self, benchmark_id: str, matching_key: str, *, originating_side: str,
    ) -> CompanyInvestigation | None:
        """Assemble a read-only investigation from existing certified artifacts."""
        comparison = self.corpus_comparison(benchmark_id)
        if not comparison.available:
            return None
        selected = next((row for row in comparison.rows if row.normalized_matching_key == matching_key), None)
        if selected is None:
            return None
        detail = self.get_benchmark(benchmark_id)
        benchmark_name = detail.benchmark_name if detail else benchmark_id
        source_rows = tuple(
            SourceEvidenceSummary(
                row.source_section, row.source_document, row.source_page, row.source_notes,
                row.duplicate_placement, row.placement_index,
            )
            for row in comparison.authored_candidates
            if _identity_name(row.company_name) == _identity_name(selected.company_name)
        )
        rce = next((
            row for row in comparison.rce_candidates
            if row.returned_rank == selected.rce_rank and selected.appears_in_rce_corpus
        ), None)
        consequence = "No candidate-level benchmark consequence recorded."
        if detail and rce:
            evaluated = next((
                row for row in detail.candidates
                if row.returned and (
                    (_ticker_keys(row.ticker) and _ticker_keys(row.ticker) & _ticker_keys(rce.ticker))
                    or _identity_name(row.company_name) == _identity_name(rce.company_name)
                )
            ), None)
            if evaluated:
                consequence = evaluated.score_consequence
        rce_summary = None if rce is None else RCECandidateSummary(
            rce.company_name, rce.ticker, rce.returned_rank, rce.returned_category,
            rce.validation_status, rce.rationale_present, rce.evidence_present, consequence,
        )
        status_labels = {
            "agreement": "Appears in both corpora",
            "authored_only": "Authored source only",
            "rce_only": "RCE discovery",
            "identity_review": "Identity requires review",
        }
        matching_method = (
            "ticker/identifier" if selected.normalized_matching_key.startswith("ticker:")
            else "normalized-name fallback" if selected.comparison_outcome == "agreement"
            else "unresolved identity"
        )
        explanation = selected.explanation
        if selected.comparison_outcome == "authored_only":
            explanation = (
                "Not returned in the stored RCE candidate corpus. "
                "The current artifact does not establish why it was omitted."
            )
        context = tuple(
            ComparisonContext(row.company_name, row.ticker_or_identifier, status_labels[row.comparison_outcome])
            for row in comparison.rows
            if row.normalized_matching_key != matching_key
        )[:6]
        return CompanyInvestigation(
            benchmark_id, benchmark_name, selected.company_name, selected.ticker_or_identifier,
            originating_side, selected.comparison_outcome, status_labels[selected.comparison_outcome],
            selected.appears_in_authored_corpus, selected.appears_in_rce_corpus, selected.rce_rank,
            matching_method, explanation, source_rows, rce_summary, context,
        )

    def approve_for_benchmark_of_record(self, benchmark_id: str, matching_key: str) -> bool:
        comparison = self.corpus_comparison(benchmark_id)
        row = next((item for item in comparison.rows if item.normalized_matching_key == matching_key), None)
        if row is None:
            raise ValueError("The selected company is not available in this benchmark comparison.")
        return self._curator_approvals.approve(benchmark_id, row)

    def approved_matching_keys(self, benchmark_id: str) -> frozenset[str]:
        return self._curator_approvals.approved_keys(benchmark_id)

    def curator_rows(self, benchmark_id: str, side: str) -> tuple[CuratorCorpusRow, ...]:
        comparison = self.corpus_comparison(benchmark_id)
        if not comparison.available:
            return ()
        approved = self.approved_matching_keys(benchmark_id)
        rows = (
            row for row in comparison.rows
            if (side == "authored" and row.appears_in_authored_corpus)
            or (side == "rce" and row.appears_in_rce_corpus)
        )
        return tuple(CuratorCorpusRow(
            row.normalized_matching_key, row.company_name, row.ticker_or_identifier,
            row.rce_rank, row.comparison_outcome,
            row.comparison_outcome == "agreement" or row.normalized_matching_key in approved,
        ) for row in rows)

    def curator_progress(self, benchmark_id: str) -> CuratorProgress:
        comparison = self.corpus_comparison(benchmark_id)
        if not comparison.available:
            return CuratorProgress(0, 0, 0, 0, 0)
        approved = self.approved_matching_keys(benchmark_id)
        curator_additions = sum(row.normalized_matching_key in approved for row in comparison.rows)
        pending_authored = sum(
            row.comparison_outcome in {"authored_only", "identity_review"}
            and row.normalized_matching_key not in approved for row in comparison.rows
        )
        pending_rce = sum(
            row.comparison_outcome == "rce_only" and row.normalized_matching_key not in approved
            for row in comparison.rows
        )
        return CuratorProgress(
            comparison.agreement_count, curator_additions, pending_authored, pending_rce,
            comparison.agreement_count + curator_additions,
        )

    def benchmark_of_record(self, benchmark_id: str) -> tuple[BenchmarkOfRecordMember, ...]:
        comparison = self.corpus_comparison(benchmark_id)
        if not comparison.available:
            return ()
        approved = self.approved_matching_keys(benchmark_id)
        members = [
            BenchmarkOfRecordMember(
                benchmark_id, row.company_name, row.ticker_or_identifier,
                "Agreement" if row.comparison_outcome == "agreement" else "Curator approval",
                row.comparison_outcome,
            )
            for row in comparison.rows
            if row.comparison_outcome == "agreement" or row.normalized_matching_key in approved
        ]
        return tuple(sorted(members, key=lambda row: row.company_name.casefold()))

    def get_benchmark(self, benchmark_id: str) -> BenchmarkDetail | None:
        run = next((row for row in self._runs if row.get("benchmark_id") == benchmark_id), None)
        if run is None:
            return None
        evaluation = run.get("evaluation") or {}
        config = run.get("scoring_config") or self._config
        weights = config.get("overall_weights", {})
        metrics = tuple(MetricExplanation(
            name, METRIC_LABELS.get(name, name.replace("_", " ").capitalize()), float(value),
            float(weights.get(name, 0.0)), float(value) * float(weights.get(name, 0.0)),
            str(evaluation.get("metric_notes", {}).get(name, "No calculation note recorded.")),
            METRIC_EXPLANATIONS.get(name, "Deterministic evaluator metric."),
        ) for name, value in evaluation.get("metrics", {}).items())
        fixture = self._fixtures.get(benchmark_id)
        reviewed = None
        if fixture:
            identity = fixture.get("benchmark", {})
            securities = tuple(_frozen(row) for row in fixture.get("securities", []))
            reviewed = ReviewedBenchmark(
                identity.get("description"), identity.get("review_notes"), identity.get("reviewed_by"),
                identity.get("source_document"), identity.get("source_date"),
                tuple(_frozen(row) for row in fixture.get("categories", [])),
                securities,
                tuple(row for row in securities if row.get("expectation") != "must_exclude"),
                tuple(row for row in securities if row.get("expectation") == "must_exclude"),
                tuple(str(value) for value in fixture.get("benchmark_caveats", [])),
                tuple(_frozen(row) for row in fixture.get("sources", [])),
            )
        candidates = tuple(self._candidate(row) for row in evaluation.get("candidate_results", []))
        categories = tuple(CategoryComparison(
            str(row.get("category_name", "")), str(row.get("expected_status", "")), float(row.get("importance", 0)),
            bool(row.get("returned")), float(row.get("coverage_credit", 0)), row.get("notes"),
        ) for row in evaluation.get("category_results", []))
        return BenchmarkDetail(
            benchmark_id, str(run.get("benchmark_name") or benchmark_id), str(run.get("benchmark_version", "")),
            str(run.get("benchmark_question", "")), str(run.get("run_label", "")), str(run.get("provider", "")),
            str(run.get("model", "")), str(run.get("prompt_version", "")), str(config.get("config_version", "unknown")),
            str(run.get("run_status") or "unknown"), run.get("overall_score"), reviewed, candidates, categories, metrics,
            tuple(str(value) for value in evaluation.get("parser_warnings", [])),
            tuple(str(value) for value in (run.get("limitations") or evaluation.get("limitations") or [])),
        )

    def review_queue(self) -> tuple[CandidateComparison, ...]:
        details = (self.get_benchmark(domain.benchmark_id) for domain in self.list_domains())
        return tuple(
            candidate
            for detail in details if detail is not None
            for candidate in detail.candidates
            if _group(candidate) == "unexpected" and candidate.reviewer_status in (None, "needs_verification")
        )
