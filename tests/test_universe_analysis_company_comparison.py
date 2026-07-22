from types import SimpleNamespace

from src.universe_analysis_streamlit_adapter import (
    build_consolidated_company_comparison_rows,
    filter_consolidated_company_rows,
)


def _ranked(ticker, rank, profile="Mixed"):
    return {
        "rank": rank, "company_name": ticker + " Company", "ticker": ticker,
        "technical_profile": profile, "trend_label": "Mixed",
        "momentum_label": "Neutral", "extension_label": "Near trend",
        "volatility_label": "Moderate", "key_signal": "Mixed evidence",
    }


def _fact(section, ticker, *, event_type=None, direction=None, value="Fact",
          priority=None, refs=("evidence:1",), matching_key=None):
    return SimpleNamespace(
        section=section, ticker=ticker, matching_key=matching_key or f"ticker:{ticker}",
        event_type=event_type, direction=direction, value=value,
        priority_tier=priority, evidence_refs=refs,
        source_identity=f"{section}:{ticker}:{event_type or 'member'}",
        company_name=ticker + " Company",
    )


def _view(*facts, status="fully_comparable"):
    names = ("current_read", "deserves_attention", "what_changed", "leaders",
             "laggards", "membership_changes", "caveats")
    return SimpleNamespace(
        comparison_status=status,
        sections=tuple(SimpleNamespace(key=name, rows=tuple(
            fact for fact in facts if fact.section == name
        )) for name in names),
    )


def test_annotations_join_by_ticker_without_changing_rank_order():
    ranked = [_ranked("BBB", 1), _ranked("AAA", 2), _ranked("CCC", 3)]
    view = _view(
        _fact("laggards", "AAA"),
        _fact("leaders", "BBB"),
        _fact("deserves_attention", "CCC", priority=2),
    )
    rows = build_consolidated_company_comparison_rows(ranked, view)

    assert [row.ticker for row in rows] == ["BBB", "AAA", "CCC"]
    assert [row.rank for row in rows] == [1, 2, 3]
    assert rows[0].intelligence == ("Leader",)
    assert rows[1].intelligence == ("Laggard",)
    assert rows[2].intelligence == ("Attention",)
    assert rows[2].attention_priority == 2


def test_added_member_is_distinct_from_deterioration_under_limited_comparison():
    ranked = [_ranked("NEW", 1, profile="Weak")]
    view = _view(
        _fact("membership_changes", "NEW", event_type="membership_added"),
        _fact("deserves_attention", "NEW", priority=1),
        status="limited_comparability",
    )
    row = build_consolidated_company_comparison_rows(ranked, view)[0]

    assert row.technical_profile == "Weak"
    assert row.membership == "Added"
    assert row.change_status == "No prior comparable member state"
    assert row.change_type is None
    assert "Membership state only" in row.comparison_limitation


def test_deterministic_change_meaning_and_references_are_preserved():
    view = _view(_fact(
        "what_changed", "AAA", event_type="technical.profile",
        direction="deteriorated", value="Strong → Weak", refs=("before", "after"),
    ))
    row = build_consolidated_company_comparison_rows([_ranked("AAA", 1)], view)[0]

    assert row.change_status == "Weakened"
    assert row.change_type == "technical.profile"
    assert row.change_summary == "Strong → Weak"
    assert row.evidence_refs == ("after", "before")
    assert row.source_identities


def test_removed_member_is_unranked_and_filterable_after_ranked_rows():
    view = _view(_fact(
        "membership_changes", "OLD", event_type="membership_removed",
        value="included → None",
    ))
    rows = build_consolidated_company_comparison_rows(
        [_ranked("AAA", 1), _ranked("BBB", 2)], view,
    )

    assert [row.ticker for row in rows] == ["AAA", "BBB", "OLD"]
    assert rows[-1].rank is None and rows[-1].membership == "Removed"
    assert [row.ticker for row in filter_consolidated_company_rows(
        rows, memberships=("Removed",),
    )] == ["OLD"]


def test_filters_only_subset_and_empty_filters_restore_every_row():
    view = _view(
        _fact("leaders", "AAA"),
        _fact("what_changed", "BBB", event_type="technical.trend", direction="changed"),
    )
    rows = build_consolidated_company_comparison_rows(
        [_ranked("AAA", 1, "Strong"), _ranked("BBB", 2, "Weak")], view,
    )

    assert [row.rank for row in filter_consolidated_company_rows(
        rows, intelligence=("Leader",),
    )] == [1]
    assert [row.rank for row in filter_consolidated_company_rows(rows, changed=True)] == [2]
    assert filter_consolidated_company_rows(rows) == rows


def test_first_observation_uses_neutral_change_state():
    row = build_consolidated_company_comparison_rows(
        [_ranked("AAA", 1)], None, first_observation=True,
    )[0]
    assert row.change_status == "First observation"
    assert row.change_type is None
