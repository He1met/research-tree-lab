"""Synthetic hand-computed accounting and chronological replay checks."""
import unittest

from researchlib.common import ContractError
from researchlib.replay import ambiguous_bar_exit, initial_state, replay_events


def event(ident, time, kind, **extra):
    return dict(event_id=ident, event_time=time, available_at=time, kind=kind, currency="USD", **extra)


class LedgerTests(unittest.TestCase):
    def test_cross_day_inventory_funding_exit_cost_and_idempotence(self):
        t1, t2 = "2026-01-01T12:00:00Z", "2026-01-02T12:00:00Z"
        fill = event("buy", t1, "fill", quantity="2", price="100", fee="1")
        first = replay_events(initial_state("1000", "USD"), [fill, event("mark1", t1, "mark", price="105")], t1)
        self.assertEqual(first["inventory"], "2")
        self.assertEqual(first["cash_excluding_costs"], "800")
        self.assertEqual(first["net_equity"], "1009")
        self.assertFalse(first["closed"])
        second = replay_events(first, [fill, event("fund", t2, "funding", amount="2"),
                                      event("mark2", t2, "mark", price="90"),
                                      event("exit", t2, "exit_cost", amount="1")], t2)
        self.assertEqual(second["inventory"], "2")
        self.assertEqual(second["net_equity"], "976")
        self.assertEqual(second["known_fees"], "1")

    def test_unknown_fee_is_unknown_never_zero(self):
        t = "2026-01-01T12:00:00Z"
        state = replay_events(initial_state("1000", "USD"), [event("buy", t, "fill", quantity="2", price="100", fee=None), event("mark", t, "mark", price="105")], t)
        self.assertEqual(state["gross_equity"], "1010")
        self.assertIsNone(state["net_equity"])
        self.assertEqual(state["unknown_cost_event_ids"], ["buy"])

    def test_future_or_unavailable_or_before_effective_data_rejected(self):
        t1, t2 = "2026-01-01T12:00:00Z", "2026-01-02T12:00:00Z"
        with self.assertRaises(ContractError):
            replay_events(initial_state(1000, "USD"), [event("future", t2, "mark", price=100)], t1)
        with self.assertRaises(ContractError):
            replay_events(initial_state(1000, "USD"), [event("old", t1, "mark", price=100)], t2, effective_from=t2)

    def test_conflicting_duplicate_or_quote_unit_rejected(self):
        t = "2026-01-01T12:00:00Z"
        e = event("same", t, "mark", price=100)
        state = replay_events(initial_state(1000, "USD"), [e], t)
        with self.assertRaises(ContractError):
            replay_events(state, [dict(e, price=200)], t)
        with self.assertRaises(ContractError):
            replay_events(state, [dict(e, event_id="eur", currency="EUR")], t)

    def test_coarse_bar_ambiguity_never_selects_favorable_fill(self):
        result = ambiguous_bar_exit(80, 120, 90, 110, "REQUIRE_FINER_DATA")
        self.assertEqual(result["state"], "PATH_AMBIGUOUS")
        self.assertIsNone(result["exit_price"])
        self.assertEqual(ambiguous_bar_exit(80, 120, 90, 110, "STOP_FIRST_CONSERVATIVE")["exit_price"], "90")

    def test_dynamic_model_decision_must_exist_before_event(self):
        t = "2026-01-01T12:00:00Z"
        e = event("buy", t, "fill", quantity=1, price=100, fee=1, requires_llm_decision=True, decision_ref="D1")
        with self.assertRaises(ContractError):
            replay_events(initial_state(1000, "USD"), [e], t)
        result = replay_events(initial_state(1000, "USD"), [e], t, required_decision_refs={"D1": {"available_at": t, "output_hash": "sealed-output"}})
        self.assertEqual(result["inventory"], "1")


if __name__ == "__main__":
    unittest.main()
