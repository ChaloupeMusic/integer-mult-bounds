#!/usr/bin/env python3
"""A cheap, source-bound entry to the selected bottleneck; not a full cold replay.

Douglas Colkitt, with OpenAI Codex assistance. Apache-2.0.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from choose_research_task import check_catalog_files
from verify_selected_result import check

ROOT = Path(__file__).resolve().parents[1]


def summarize(record, certificate, target=Fraction(1, 100)):
    if not 0 < target < 1:
        raise ValueError("target kappa must be between zero and one")
    bit, complex_ = Fraction(certificate["bit_lower"]), Fraction(certificate["complex_lower"])
    if bit <= 0 or complex_ <= 0:
        raise ValueError("supplier savings must be positive")
    required = target / (1 - target)
    return {
        "status": "PASS_RESEARCH_BASELINE_BINDINGS_ONLY",
        "selected_kappa": record["kappa"], "review": record["review"],
        "certificate": record["certificate"], "full_replay": record["reproduce"],
        "bit_saving": str(bit), "complex_saving": str(complex_),
        "binding_primitive": "bit" if bit < complex_ else "complex" if complex_ < bit else "equal",
        "ideal_balanced_cap": str(min(bit, complex_) / (1 + min(bit, complex_))),
        "target_kappa": str(target), "target_primitive_under_retained_transfer": str(required),
        "required_bit_multiplier": float(required / bit),
        "required_complex_multiplier": float(required / complex_),
        "scope": "Selected source bindings and arithmetic only. The a/(1+a) transfer is a planning model under retained hypotheses, not a universal requirement or supplier verification.",
    }


def selected_inputs(record, root=ROOT):
    """Repository paths the selected-record check reads, before it reads them."""
    names = [record["certificate"], record["source_manifest"], record["proof"],
             record["review"], record["validation"], *record["proof_supplements"]]
    check_catalog_files(root, [(names[1], "Invalid selected file: " + names[1])])
    manifest = root / record["source_manifest"]
    if manifest.is_file():
        raw = manifest.read_bytes()
    else:  # a sparse omission whose HEAD blob matches the index (checked above)
        raw = subprocess.run(["git", "cat-file", "blob", "HEAD:" + record["source_manifest"]],
                             cwd=root, check=True, capture_output=True).stdout
    inventory = json.loads(raw)
    if inventory.get("format") == "repository-packages-sha256-v1":
        names += inventory["files"]
    else:
        parent = Path(record["source_manifest"]).parent
        names += [(parent / name).as_posix() for name in inventory["files"]]
    return sorted(set(names))


def sparse_omissions(record, root=ROOT):
    """Selected inputs absent only because this is a sparse checkout.

    Uses the chooser's PR3102 contract: each absent path must be a stage-zero
    regular skip-worktree entry whose blob matches HEAD. A deletion, staged drift
    or unknown path raises the usual "Invalid selected file" error instead.
    """
    names = selected_inputs(record, root)
    return check_catalog_files(root, [(name, "Invalid selected file: " + name) for name in names])


def materialize_command(omitted):
    """Cone-mode directories covering the omitted files (one research package each)."""
    dirs = set()
    for name in omitted:
        parts = name.split("/")
        dirs.add("/".join(parts[:2]) if parts[0] == "research" and len(parts) > 2 else "/".join(parts[:-1]) or ".")
    return ["git", "sparse-checkout", "add", *sorted(dirs)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="1/100", help="rational target kappa for planning")
    args = ap.parse_args()
    raw = (ROOT / "certificates/selected-result.json").read_bytes()
    record = json.loads(raw)
    omitted = sparse_omissions(record)
    if omitted:
        print(json.dumps({
            "status": "SPARSE_SELECTED_INPUTS_ABSENT",
            "omitted_files": len(omitted), "first_omitted": omitted[:5],
            "materialize": materialize_command(omitted),
            "scope": "This sparse checkout omits selected inputs (skip-worktree entries matching HEAD). Run the materialize command, then rerun; nothing was verified.",
        }, indent=2))
        sys.exit(2)
    check(record, ROOT)
    certificate = json.loads((ROOT / record["certificate"]).read_bytes())
    report = summarize(record, certificate, Fraction(args.target))
    report["selected_record_sha256"] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
