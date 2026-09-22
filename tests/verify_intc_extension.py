#!/usr/bin/env python3
"""B02 isolated SYNTHETIC extension against a copy of current committed records.

Run: python3 tests/verify_intc_extension.py --receipt tests/receipts/intc-extension.json
Never changes live product configuration, records, source, or native automations.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from researchlib import Store, publish_snapshot
from researchlib.common import canonical, digest, now_iso, read_json
from researchlib.snapshot import project, verify_snapshot
from native_receipts import read_installed
from publish import source_hash

PROMPTS = ("01_DISCOVERY.txt", "02_RESEARCH.txt", "03_DAILY_REVIEW.txt", "04_PUBLISH.txt")


def tree_hash(root):
    return digest(canonical({p.relative_to(root).as_posix(): digest(p.read_bytes())
                             for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}))


def state_hashes(root, live_store=None):
    result = {
        "product_config": digest((root / "config/products.json").read_bytes()),
        "web_src": tree_hash(root / "web/src"),
        "core_researchlib": tree_hash(root / "researchlib"),
        "core_scripts": tree_hash(root / "scripts"),
        "project_skills": tree_hash(root / ".agents/skills"),
        "four_project_prompts": {name: digest((root / "prompts" / name).read_bytes()) for name in PROMPTS},
    }
    if live_store:
        result["committed_store"] = tree_hash(live_store / "bundles")
        result["approved_source_implementation"] = source_hash()
        result["four_installed_native_prompts"] = {r["logical_key"]: r["prompt_sha256"] for r in read_installed()}
    return result


def run_verification():
    installation = read_json(ROOT / ".local/installation.json")
    live_store = Path(installation["store_root"])
    before = state_hashes(ROOT, live_store)
    if before["approved_source_implementation"] != installation["approved_source_sha256"]:
        raise AssertionError("Approved implementation already differs before this test")
    live_products = read_json(ROOT / "config/products.json")
    if any(p["product_id"] == "intc" for p in live_products["products"]):
        raise AssertionError("B02 expects INTC absent from the live registered intent list")

    with tempfile.TemporaryDirectory(prefix="research-b02-isolated-") as temporary:
        isolated = (Path(temporary) / "project-copy").resolve()
        isolated.mkdir()
        for relative in ("researchlib", "scripts", "web/src", ".agents/skills", "prompts"):
            shutil.copytree(ROOT / relative, isolated / relative, ignore=shutil.ignore_patterns("__pycache__"))
        (isolated / "config").mkdir()
        shutil.copy2(ROOT / "config/products.json", isolated / "config/products.json")
        shutil.copytree(live_store / "bundles", isolated / ".local/store/bundles")
        store = Store(isolated)
        assert store.root.is_relative_to(isolated) and store.root != live_store.resolve()
        baseline_at = now_iso()
        records_before, _, anomalies = store.load(strict=True)
        assert not anomalies
        plans_before = {ref: digest(canonical(record)) for ref, record in records_before.items() if record["record_type"] == "plan"}
        isolated_before = state_hashes(isolated)
        output = isolated / "public-data"
        old = publish_snapshot(store, output, baseline_at)
        old_catalog_bytes = (output / old["catalog_url"]).read_bytes()
        old_catalog = json.loads(old_catalog_bytes)
        assert not any(p["product_id"] == "intc" for p in old_catalog["products"])

        mapping = {
            "schema_version": "1.0", "fixture_provenance": "SYNTHETIC_ENGINEERING_ONLY",
            "product_id": "intc", "source_id": "intc-isolated-source-fixture",
            "source_url": None, "native_contract_code": None, "verified": False,
            "data_role": "TARGET_UNVERIFIED", "license": "OWN_ANALYSIS",
            "scope": "Schema and publication extension only; no actual contract or data claim",
        }
        fixture_product = {
            "product_id": "intc", "display_name": "INTC · SYNTHETIC 扩展验证", "ticker": "INTC",
            "underlying_kind": "us_equity", "research_intent": "perpetual", "enabled": False,
            "status": "SYNTHETIC_UNVERIFIED_NOT_ENABLED", "instrument_refs": [], "dataset_refs": [],
            "source_mapping_ref": "config/source-mappings/intc-synthetic.json",
        }
        extended_config = read_json(isolated / "config/products.json")
        extended_config["products"].append(fixture_product)
        extended_config["fixture_provenance"] = "SYNTHETIC_ISOLATED_COPY_ONLY"
        (isolated / "config/products.json").write_bytes(canonical(extended_config))
        mapping_file = isolated / fixture_product["source_mapping_ref"]
        mapping_file.parent.mkdir(parents=True)
        mapping_file.write_bytes(canonical(mapping))
        extension_at = now_iso()
        # false exercises the actual production projection filter inside this
        # throwaway copy; displayed stage/name and receipt explicitly say SYNTHETIC.
        # This object must never be admitted to the real store.
        product_record = {
            "schema_version": "1.0", "record_type": "product", "product_id": fixture_product["product_id"],
            "spec_version": "isolated-engineering-v1", "created_at": extension_at, "available_at": extension_at,
            "synthetic": False, "display_name": fixture_product["display_name"], "enabled": False, "active": False,
            "status": fixture_product["status"], "verification_status": "SYNTHETIC_UNVERIFIED",
            "evidence_stage": "SYNTHETIC_ENGINEERING_ONLY", "instrument_ref": None, "native_code": None,
            "data_sources": [read_json(mapping_file)],
            "disclosure": {"visibility": "PUBLIC", "license": "OWN_ANALYSIS"},
        }
        store.commit_bundle("b02-intc-isolated-fixture", "research", [product_record],
                            request_key="SYNTHETIC-B02-ISOLATED-ONLY")
        records_after, _, anomalies = store.load(strict=True)
        assert not anomalies
        plans_after = {ref: digest(canonical(record)) for ref, record in records_after.items() if record["record_type"] == "plan"}
        assert plans_before == plans_after
        new = publish_snapshot(store, output, now_iso())
        verify_snapshot(output, new["snapshot_id"])
        new_catalog = read_json(output / new["catalog_url"])
        matching = [p for p in new_catalog["products"] if p["product_id"] == "intc"]
        assert len(matching) == 1 and matching[0]["data_sources"] == [mapping]
        assert matching[0]["active"] is False and matching[0]["native_code"] is None
        assert new["record_count"] == old["record_count"] + 1
        assert new["round_count"] == old["round_count"]
        historical = project(store, baseline_at)[0]
        assert not any(p["product_id"] == "intc" for p in historical["products"])
        assert (output / old["catalog_url"]).read_bytes() == old_catalog_bytes
        isolated_after = state_hashes(isolated)
        assert isolated_before["product_config"] != isolated_after["product_config"]
        for key in ("web_src", "core_researchlib", "core_scripts", "project_skills", "four_project_prompts"):
            assert isolated_before[key] == isolated_after[key]
        isolation_evidence = {
            "record_count_before": len(records_before), "record_count_after": len(records_after),
            "old_plan_refs": sorted(plans_before), "old_plan_hashes": plans_before,
            "old_plan_set_and_bytes_unchanged": plans_before == plans_after,
            "snapshot_before": old["snapshot_id"], "snapshot_after": new["snapshot_id"],
            "historical_as_of": baseline_at, "extension_record_created_at": extension_at,
            "old_snapshot_and_historical_products_unchanged": True, "new_product_visible": True,
            "new_source_mapping_visible": True, "round_count_unchanged": True,
            "isolated_hashes_before": isolated_before, "isolated_hashes_after": isolated_after,
            "fixture_product": product_record,
        }
    after = state_hashes(ROOT, live_store)
    assert before == after, "Live project or native prompt changed during the isolated verification"
    assert read_json(ROOT / ".local/installation.json")["approved_source_sha256"] == installation["approved_source_sha256"]
    return {
        "schema_version": "1.0", "acceptance_id": "B02", "status": "PASS_ISOLATED_ENGINEERING",
        "provenance": "SYNTHETIC_FIXTURE_AGAINST_COPY_OF_REAL_COMMITTED_RECORDS",
        "verified_at": now_iso(), "runtime": {"python": platform.python_version(), "os": platform.system(), "machine": platform.machine()},
        "production_before": before, "production_after": after, "production_unchanged": True,
        "approved_source_sha256_unchanged": True, "isolated": isolation_evidence,
        "limitations": [
            "No real INTC contract, market source, execution conditions or production activation was verified.",
            "The throwaway product uses synthetic:false solely to exercise production projection; its visible name/stage explicitly label it SYNTHETIC.",
            "Product intent/source mapping configuration alone is not auto-imported by the publisher; the discovery/research role must submit the corresponding immutable product record.",
            "This checks configurable file-to-snapshot extension and historical exclusion, not INTC economic evidence or a natural scheduled run.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", default="tests/receipts/intc-extension.json")
    args = parser.parse_args()
    receipt = run_verification()
    from public_guard import check_paths
    destination = ROOT / args.receipt
    if not destination.resolve().is_relative_to(ROOT / "tests"):
        raise ValueError("Receipt destination must remain under tests/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical(receipt))
    if check_paths([destination.relative_to(ROOT).as_posix()]):
        raise ValueError("Receipt failed public disclosure scan")
    print(json.dumps({"acceptance_id": "B02", "status": receipt["status"], "production_unchanged": True,
                      "approved_source_sha256_unchanged": True, "old_plan_count": len(receipt["isolated"]["old_plan_refs"]),
                      "isolated_records_before": receipt["isolated"]["record_count_before"],
                      "isolated_records_after": receipt["isolated"]["record_count_after"],
                      "receipt": destination.relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2))
