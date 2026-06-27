import unittest

from src.contract_quality import ALL_PASSED_NO, ALL_PASSED_YES
from src.quality_diagnostics import (
    PASSING_CONTRACTS_POPULATION,
    REJECTED_CONTRACTS_POPULATION,
    TRUE_NEAR_MISS_CONTRACTS_POPULATION,
    comparison_quality_variable_distributions,
    distribution_population,
    quality_variable_distributions,
)
from src.rule_evaluation import FAIL, PASS


def contract(
    *,
    all_passed,
    delta_fit,
    spread_pass,
    volume_pass,
    open_interest_pass,
    delta,
    spread_percent,
    volume,
    open_interest,
):
    return {
        "All Passed": all_passed,
        "Delta Fit": delta_fit,
        "Spread Pass": spread_pass,
        "Volume Pass": volume_pass,
        "Open Interest Pass": open_interest_pass,
        "Delta": delta,
        "Spread %": spread_percent,
        "Volume": volume,
        "Open Interest": open_interest,
    }


class QualityDiagnosticsDistributionTest(unittest.TestCase):
    def setUp(self):
        self.passing = contract(
            all_passed=ALL_PASSED_YES,
            delta_fit=PASS,
            spread_pass=PASS,
            volume_pass=PASS,
            open_interest_pass=PASS,
            delta=0.55,
            spread_percent=0.02,
            volume=750,
            open_interest=1_500,
        )
        self.true_near_miss = contract(
            all_passed=ALL_PASSED_NO,
            delta_fit=FAIL,
            spread_pass=PASS,
            volume_pass=PASS,
            open_interest_pass=PASS,
            delta=0.45,
            spread_percent=0.03,
            volume=600,
            open_interest=1_200,
        )
        self.rejected = contract(
            all_passed=ALL_PASSED_NO,
            delta_fit=FAIL,
            spread_pass=FAIL,
            volume_pass=FAIL,
            open_interest_pass=PASS,
            delta=0.15,
            spread_percent=0.12,
            volume=0,
            open_interest=1_100,
        )
        self.rows = [self.passing, self.true_near_miss, self.rejected]

    def test_distribution_population_uses_existing_status_definitions(self):
        self.assertEqual(
            distribution_population(self.rows, PASSING_CONTRACTS_POPULATION),
            [self.passing],
        )
        self.assertEqual(
            distribution_population(self.rows, TRUE_NEAR_MISS_CONTRACTS_POPULATION),
            [self.true_near_miss],
        )
        self.assertEqual(
            distribution_population(self.rows, REJECTED_CONTRACTS_POPULATION),
            [self.rejected],
        )

    def test_single_population_distributions_keep_bucket_order_and_zone_context(self):
        delta_rows = quality_variable_distributions([self.passing])["Delta Distribution"]

        self.assertEqual([row["Bucket"] for row in delta_rows[:4]], [
            "< 0.20",
            "0.20-0.30",
            "0.30-0.40",
            "0.40-0.45",
        ])
        pass_bucket = next(row for row in delta_rows if row["Bucket"] == "0.50-0.60")
        self.assertEqual(pass_bucket["Zone"], "Pass Zone")
        self.assertEqual(pass_bucket["Count"], 1)
        self.assertEqual(pass_bucket["Percentage"], 1.0)

    def test_comparison_distributions_share_buckets_and_include_counts_and_percentages(self):
        comparison = comparison_quality_variable_distributions(
            self.rows,
            REJECTED_CONTRACTS_POPULATION,
            PASSING_CONTRACTS_POPULATION,
        )
        volume_rows = comparison["Volume Distribution"]

        self.assertEqual(
            [row["Bucket"] for row in volume_rows],
            ["0", "1-100", "101-250", "251-500", "501-1,000", "1,001-2,500", "> 2,500"],
        )
        rejected_bucket = next(row for row in volume_rows if row["Bucket"] == "0")
        passing_bucket = next(row for row in volume_rows if row["Bucket"] == "501-1,000")

        self.assertEqual(rejected_bucket["Rejected Count"], 1)
        self.assertEqual(rejected_bucket["Rejected %"], 1.0)
        self.assertEqual(rejected_bucket["Passing Count"], 0)
        self.assertEqual(passing_bucket["Rejected Count"], 0)
        self.assertEqual(passing_bucket["Passing Count"], 1)
        self.assertEqual(passing_bucket["Passing %"], 1.0)


if __name__ == "__main__":
    unittest.main()
