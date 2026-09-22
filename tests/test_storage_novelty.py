"""SYNTHETIC A03 perturbations through the production file projection."""
import copy
import tempfile
import unittest

from researchlib import Store
from researchlib.common import digest
from researchlib.snapshot import project

NOW = "2026-01-01T00:00:00Z"


def record(kind, **fields):
    return dict(schema_version="1.0", record_type=kind, created_at=NOW, available_at=NOW,
                synthetic=False, disclosure={"visibility": "PUBLIC", "license": "OWN_ANALYSIS"}, **fields)


def candidate(ident, product="BTC", lookback=20, dataset="D1", method="M1"):
    round_record = record("round", round_id="R" + ident, question="Question " + ident,
                          title="Title " + ident, mechanism="Free-text mechanism " + ident,
                          product_refs=[product], parent_round_id=None, plan_refs=["P" + ident + "@1"])
    plan = record("plan", plan_id="P" + ident, version=1, round_id="R" + ident,
                  product_refs=[product], instrument_ref=product + "-TARGET", dataset_refs=[dataset], method_ref=method,
                  sample_role="DEVELOPMENT", parameters={"lookback": lookback},
                  rules={"signal": {"operator": "gt", "left": "close", "right": {"indicator": "rolling_high", "lookback": lookback}},
                         "entry": {"event": "next_open", "ticker": product}, "quantity_or_inventory": {"quantity": 1},
                         "exit": {"event": "time_stop", "bars": 12}, "reentry": {"allowed": False},
                         "termination": {"event": "fixed_window_end"}}, replay_eligibility="UNKNOWN")
    return round_record, plan


class NoveltyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name, clock=lambda: NOW)
        methods = [record("method", method_id=name, algorithm={"operator": "rolling_high_comparison", "parameters": {"lookback": 20}}) for name in ("M1", "M-renamed")]
        datasets = [record("dataset", dataset_id=name, data_ref="sha256:" + digest(data.encode()), data_role="TARGET",
                           instrument_ref=product + "-TARGET", columns=["time", "close"], units="USD", granularity="1h")
                    for name, product, data in (("D1", "BTC", "same input"), ("D-renamed", "BTC", "same input"),
                                               ("D2", "BTC", "new sample"), ("D-ETH", "ETH", "other product"))]
        self.store.commit_bundle("support", "research", methods + datasets)

    def tearDown(self):
        self.tmp.cleanup()

    def project_candidates(self, *pairs):
        self.store.commit_bundle("candidates", "research", [r for pair in pairs for r in pair])
        catalog, details, _, _ = project(self.store, NOW)
        return catalog, {node["id"]: node for node in catalog["nodes"]}, details

    def test_renaming_title_free_text_method_and_dataset_ids_is_not_novelty(self):
        first = candidate("1")
        second = candidate("2", dataset="D-renamed", method="M-renamed")
        second[0]["mechanism_fingerprint"] = "user-asserted-new-family"
        catalog, nodes, _ = self.project_candidates(first, second)
        self.assertEqual(catalog["mechanism_family_count"], 1)
        self.assertEqual(nodes["R1"]["mechanism_fingerprint"], nodes["R2"]["mechanism_fingerprint"])
        self.assertEqual(nodes["R2"]["originality"], "DUPLICATE_RULES_AND_INPUTS")
        self.assertIsNone(catalog["scientifically_independent_mechanism_count"])

    def test_numeric_parameter_tuning_is_variant_inside_same_family(self):
        catalog, nodes, _ = self.project_candidates(candidate("1"), candidate("2", lookback=21))
        self.assertEqual(catalog["mechanism_family_count"], 1)
        self.assertNotEqual(nodes["R1"]["novelty_comparison"]["variant_signature"], nodes["R2"]["novelty_comparison"]["variant_signature"])
        self.assertEqual(nodes["R2"]["originality"], "PARAMETER_OR_RULE_VARIANT")

    def test_same_rules_other_product_is_replication_candidate(self):
        catalog, nodes, _ = self.project_candidates(candidate("1"), candidate("2", product="ETH", dataset="D-ETH"))
        self.assertEqual(catalog["mechanism_family_count"], 1)
        self.assertEqual(nodes["R2"]["originality"], "CROSS_PRODUCT_REPLICATION_CANDIDATE")

    def test_same_rules_new_data_is_new_sample_candidate(self):
        catalog, nodes, _ = self.project_candidates(candidate("1"), candidate("2", dataset="D2"))
        self.assertEqual(catalog["mechanism_family_count"], 1)
        self.assertEqual(nodes["R2"]["originality"], "NEW_SAMPLE_REPLICATION_CANDIDATE")

    def test_many_sources_are_one_round_and_do_not_change_signature(self):
        pair = candidate("1")
        pair[0]["additional_source_refs"] = ["source-a", "source-b", "source-c"]
        catalog, nodes, _ = self.project_candidates(pair)
        self.assertEqual(catalog["round_count"], 1)
        self.assertEqual(catalog["mechanism_family_count"], 1)
        self.assertEqual(nodes["R1"]["originality"], "UNKNOWN_NOVELTY")
        from researchlib.novelty import plan_signature
        signature = plan_signature(pair[1], self.store.load()[0])
        renamed = copy.deepcopy(pair[1])
        renamed["title"] = "Another display title"
        self.assertEqual(signature, plan_signature(renamed, self.store.load()[0]))

    def test_unresolved_dataset_identity_cannot_be_claimed_exact_duplicate(self):
        _, nodes, _ = self.project_candidates(candidate("1", dataset="unresolved-A"), candidate("2", dataset="unresolved-B"))
        self.assertEqual(nodes["R2"]["originality"], "DUPLICATE_RULES_INPUTS_UNVERIFIED")
        self.assertFalse(nodes["R2"]["novelty_comparison"]["input_identity_known"])

    def test_prose_only_unique_names_are_unknown_and_not_counted_independent(self):
        r1 = candidate("1")[0]
        r2 = candidate("2")[0]
        r1["plan_refs"], r2["plan_refs"] = [], []
        catalog, nodes, _ = self.project_candidates((r1,), (r2,))
        self.assertEqual(catalog["mechanism_family_count"], 0)
        self.assertTrue(all(node["originality"] == "UNKNOWN_NOVELTY" for node in nodes.values()))
        self.assertTrue(all(node["mechanism_fingerprint"] is None for node in nodes.values()))

    def test_declaration_and_traceable_evidence_do_not_self_certify_novelty(self):
        source = record("evidence", evidence_id="novelty-source", summary="Public source research")
        self.store.commit_bundle("source", "research", [source])
        pair = candidate("1")
        pair[0].update(mechanism_identity={"family": "declared-mechanism"}, novelty_claim="New mechanism",
                       novelty_evidence_refs=["novelty-source", "unknown-source"], replication_of="missing-prior-round")
        _, nodes, details = self.project_candidates(pair)
        node = nodes["R1"]
        self.assertEqual(node["originality"], "DECLARED_UNVERIFIED")
        self.assertEqual(node["novelty_comparison"]["traceable_evidence_refs"], ["novelty-source"])
        self.assertEqual(node["novelty_comparison"]["unresolved_evidence_refs"], ["unknown-source"])
        self.assertEqual(node["novelty_comparison"]["declared_relation"]["reference_state"], "UNRESOLVED")
        self.assertEqual(details["R1"]["originality"], "DECLARED_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
