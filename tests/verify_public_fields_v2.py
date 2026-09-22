#!/usr/bin/env python3
"""Read real committed evidence; export/restore only inside a disposable directory.

The receipt is engineering evidence, not publication or economic reproduction.
Run from this candidate checkout with --code-root pointing to installed main.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from researchlib.archive import export_backup, inspect_backup, restore_backup
from researchlib.common import canonical, digest, now_iso, read_json
from researchlib.contracts import validate_relationships
from researchlib.public import public_record, scan_bytes
from researchlib.store import Store


class ReadOnlyInstalledStore:
    """Expose only the existing reader; do not run Store's mkdir constructor."""
    def __init__(self, code_root):
        self.code_root = code_root.resolve(strict=True)
        self.installation_path = self.code_root / ".local/installation.json"
        installation = read_json(self.installation_path)
        if Path(installation["code_root"]).resolve(strict=True) != self.code_root:
            raise ValueError("Installed code root does not match requested source")
        self.root = Path(installation["store_root"]).resolve(strict=True)
        self.data_root = Path(installation["data_root"]).resolve(strict=True)
        if self.root == ROOT or self.root.is_relative_to(ROOT):
            raise ValueError("Expected installed evidence outside candidate checkout")

    def load(self, strict=False):
        return Store.load(self, strict=strict)

    def _read_bundle(self, directory):
        return Store._read_bundle(self, directory)


def tree_hashes(directory):
    return {p.relative_to(directory).as_posix(): digest(p.read_bytes())
            for p in sorted(directory.rglob("*")) if p.is_file()}


def verify(code_root):
    store = ReadOnlyInstalledStore(code_root)
    before_files = tree_hashes(store.root / "bundles")
    installed_paths = ["researchlib/public.py", "researchlib/contracts.py", ".local/installation.json"]
    installed_before = {p: digest((store.code_root / p).read_bytes()) for p in installed_paths}
    records, metadata, anomalies = store.load(strict=True)
    assert not anomalies
    validate_relationships(records)
    completion = read_json(store.code_root / "docs/second-native-research-completion.json")
    new = completion["new_public_record_metadata"]
    assert len(new) == 9
    assert all(metadata[ref]["record_hash"] == value["record_hash"] for ref, value in new.items())
    public = {ref: r for ref, r in records.items() if public_record(r) is not None}
    old = set(public) - set(new)
    assert len(public) == 48 and len(old) == 39

    spec = importlib.util.spec_from_file_location(
        "researchlib._installed_public_comparison", store.code_root / "researchlib/public.py")
    installed_public = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installed_public)
    comparisons = []
    for ref, original in sorted(public.items()):
        prior = installed_public.public_record(original)
        candidate = public_record(original)
        assert candidate == original
        assert all(candidate[k] == v for k, v in prior.items())
        if ref in old:
            assert prior == candidate
        comparisons.append({"record_ref": ref, "original_sha256": metadata[ref]["record_hash"],
                            "candidate_exact": True, "old_exported_values_unchanged": True,
                            "prior_omitted_fields": sorted(set(original) - set(prior))})
    affected = [x["record_ref"] for x in comparisons if x["prior_omitted_fields"]]
    assert len(affected) == 4
    protocols = records["m-btc-entry-confirmation-component-20260923@1"]["protocol_refs"]
    forbidden_protocol_paths = {"evidence/" + ref.removeprefix("bundle:") for ref in protocols}
    cases = [(ref, [ref]) for ref in affected]
    cases += [("all-nine-new-public", sorted(new)), ("all-forty-eight-public", sorted(public))]
    results = []
    with tempfile.TemporaryDirectory(prefix="real-public-fields-v2-readonly-") as scratch:
        scratch = Path(scratch).resolve()
        assert not scratch.is_relative_to(store.root) and not scratch.is_relative_to(store.data_root)
        for index, (label, refs) in enumerate(cases):
            a, b = scratch / f"{index}-a.zip", scratch / f"{index}-b.zip"
            first = export_backup(store, a, refs)
            second = export_backup(store, b, list(reversed(refs)))
            assert first["archive_id"] == second["archive_id"] and a.read_bytes() == b.read_bytes()
            assert inspect_backup(a)["archive_id"] == first["archive_id"]
            output = scratch / f"{index}-restored"
            recovered = restore_backup(a, output)
            for ref in recovered["record_refs"]:
                raw = (output / "records" / (ref + ".json")).read_bytes()
                assert raw == canonical(records[ref]) and digest(raw) == metadata[ref]["record_hash"]
            files = {f["path"] for f in first["files"]}
            assert not (files & forbidden_protocol_paths)
            assert not any("/PRIVATE/" in path for path in files)
            allowed_attachments = set()
            for ref in first["record_refs"]:
                bundle = metadata[ref]["bundle_id"]
                allowed_attachments.update("evidence/" + bundle + "/" + relative
                                           for relative in records[ref]["disclosure"].get("public_attachments", []))
            assert {p for p in files if p.startswith("evidence/")} <= allowed_attachments
            run_method = None
            if len(refs) == 1 and records[refs[0]]["record_type"] == "run":
                run_method = records[refs[0]]["method_ref"]
                assert run_method in first["record_refs"]
            with zipfile.ZipFile(a) as contents:
                assert set(contents.namelist()) == files | {"ARCHIVE_MANIFEST.json"}
            results.append({"case": label, "requested_refs": refs,
                            "archive_id": first["archive_id"], "archive_sha256": first["archive_sha256"],
                            "record_refs": first["record_refs"], "record_count": len(first["record_refs"]),
                            "file_count": len(first["files"]), "same_input_byte_determinism": "PASS",
                            "inspect": "PASS", "new_directory_exact_restore": "PASS",
                            "single_run_method_in_closure": run_method,
                            "unallowlisted_protocol_files_excluded": True,
                            "private_attachment_files_excluded": True,
                            "attachment_allowlist_not_expanded": True})
    after_files = tree_hashes(store.root / "bundles")
    installed_after = {p: digest((store.code_root / p).read_bytes()) for p in installed_paths}
    assert before_files == after_files and installed_before == installed_after
    final_records, final_metadata, final_anomalies = store.load(strict=True)
    assert not final_anomalies and final_records == records and final_metadata == metadata
    return {"schema_version": "1.0", "state": "PASS_ISOLATED_CANDIDATE_NOT_INSTALLED",
            "observed_at": now_iso(), "scope": "REAL_COMMITTED_RECORDS_READ_ONLY_LOCAL_SCRATCH_ARCHIVE_VERIFICATION",
            "production_records": len(records), "public_records_compared": len(public),
            "old_public_records_unchanged": len(old), "new_public_records_exact": len(new),
            "former_failures_now_exact": len(affected), "comparisons": comparisons, "cases": results,
            "candidate_source_hashes": {p: digest((ROOT / p).read_bytes()) for p in
                                        ("researchlib/public.py", "researchlib/contracts.py")},
            "installed_source_hashes_unchanged": {p: h for p, h in installed_before.items()
                                                 if p != ".local/installation.json"},
            "installation_unchanged": True, "original_files_unchanged": len(before_files),
            "committed_store_tree_sha256_before": digest(canonical(before_files)),
            "committed_store_tree_sha256_after": digest(canonical(after_files)),
            "production_writes": False, "remote_calls": False, "published": False,
            "archives_retained": False, "scientific_reproduction": "NOT_RUN",
            "limitations": ["Candidate only; independent review and installation not performed.",
                            "Exact public records and explicitly allowed attachments only; protocol/code/source originals remain excluded unless already allowlisted.",
                            "Local recovery is not remote recovery, economic validation or natural-run evidence."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True, help="Installed main root; read only")
    parser.add_argument("--receipt", type=Path, required=True, help="New receipt under this checkout's tests/receipts")
    args = parser.parse_args()
    destination = args.receipt.resolve()
    if not destination.is_relative_to((ROOT / "tests/receipts").resolve()) or destination.exists():
        parser.error("Receipt must be a new file under candidate tests/receipts")
    result = verify(args.code_root)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    scan_bytes("receipt.json", raw)
    with destination.open("xb") as output:
        output.write(raw)
    print(json.dumps({"state": result["state"], "old_public": result["old_public_records_unchanged"],
                      "new_public": result["new_public_records_exact"], "former_failures": result["former_failures_now_exact"],
                      "archive_cases": len(result["cases"]), "receipt_sha256": digest(raw)}))


if __name__ == "__main__":
    main()
