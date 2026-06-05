from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from nlp_term.schemas import (
    ChatInput,
    ChatOutput,
    ClassificationInput,
    ClassificationOutput,
    ClassificationExample,
    KnowledgeDoc,
    LabelAudit,
    ModelCandidate,
    QAExample,
    RealtimeOutput,
    RawSource,
    SourceVerification,
)


ModelT = TypeVar("ModelT", bound=BaseModel)
BANNED_OUTPUT_TERMS = ("dry-run", "dry_run", "stub", "parser 미구현", "제출 구현에서는")


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, rows: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [row.model_dump() for row in rows]
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def validate_rows(path: Path, model_type: type[ModelT], *, required: bool = True) -> list[ModelT]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    return [model_type.model_validate(row) for row in payload]


def validate_inputs(data_dir: Path, *, require_realtime: bool = False) -> None:
    validate_rows(data_dir / "test_cls.json", ClassificationInput, required=True)
    validate_rows(data_dir / "test_chat.json", ChatInput, required=True)
    validate_rows(data_dir / "test_realtime.json", ChatInput, required=require_realtime)


def validate_outputs(outputs_dir: Path, *, require_realtime: bool = False) -> None:
    validate_rows(outputs_dir / "cls_output.json", ClassificationOutput, required=True)
    validate_rows(outputs_dir / "chat_output.json", ChatOutput, required=True)
    validate_rows(outputs_dir / "realtime_output.json", RealtimeOutput, required=require_realtime)


def validate_seed_data(data_dir: Path) -> None:
    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    examples = validate_rows(data_dir / "cls_train_seed.json", ClassificationExample, required=True)
    audits = validate_rows(data_dir / "label_audit_seed.json", LabelAudit, required=True)
    qa_rows = validate_rows(data_dir / "qa_seed.json", QAExample, required=True)
    if {doc.label for doc in docs} != {0, 1, 2, 3, 4}:
        raise ValueError("knowledge_seed.json must cover labels 0-4")
    if any(not row.validated for row in examples):
        raise ValueError("cls_train_seed.json contains unvalidated examples")
    if any(row.decision != "accept" for row in audits):
        raise ValueError("label_audit_seed.json contains non-accepted audit rows")
    if any(not row.validated for row in qa_rows):
        raise ValueError("qa_seed.json contains unvalidated rows")


def validate_source_probe(path: Path, *, require_raw_files: bool = False) -> None:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON list")
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError(f"{path} rows must be objects")
        raw = RawSource.model_validate(row.get("raw"))
        SourceVerification.model_validate(row.get("verification"))
        raw_path = Path(raw.raw_path)
        if require_raw_files:
            if not raw_path.exists():
                raise FileNotFoundError(raw.raw_path)
            if raw.status_code is None or not 200 <= raw.status_code < 300:
                raise ValueError(f"{raw.source_id} has non-2xx status: {raw.status_code}")
            checksum = sha256(raw_path.read_bytes()).hexdigest()
            if checksum != raw.checksum:
                raise ValueError(f"{raw.source_id} checksum does not match raw file")


def validate_knowledge_provenance(
    data_dir: Path,
    source_probe_path: Path,
    *,
    require_official_chain: bool = False,
) -> None:
    probe_payload = read_json(source_probe_path)
    if not isinstance(probe_payload, list):
        raise ValueError(f"{source_probe_path} must contain a JSON list")
    source_map: dict[str, tuple[RawSource, SourceVerification]] = {}
    for row in probe_payload:
        raw = RawSource.model_validate(row.get("raw"))
        verification = SourceVerification.model_validate(row.get("verification"))
        source_map[raw.source_id] = (raw, verification)
    docs = validate_rows(data_dir / "knowledge_seed.json", KnowledgeDoc, required=True)
    for doc in docs:
        if doc.source_id not in source_map:
            raise ValueError(f"{doc.doc_id} references missing source_id {doc.source_id}")
        raw, verification = source_map[doc.source_id]
        if raw.status_code is not None and not 200 <= raw.status_code < 300:
            raise ValueError(f"{doc.doc_id} source has non-2xx status: {raw.status_code}")
        if require_official_chain and not verification.official_chain_ok:
            raise ValueError(f"{doc.doc_id} source is not official-chain verified")


def validate_model_shortlist(path: Path) -> None:
    rows = validate_rows(path, ModelCandidate, required=True)
    if not any(row.status == "primary" for row in rows):
        raise ValueError("model shortlist needs one primary candidate")
    if any(row.max_params_b > 9 and row.status in {"primary", "candidate"} for row in rows):
        raise ValueError("primary/candidate models must stay at or below 9B parameters")


def validate_final_readiness(outputs_dir: Path) -> None:
    for filename in ("chat_output.json", "realtime_output.json"):
        path = outputs_dir / filename
        text = path.read_text(encoding="utf-8").lower()
        for term in BANNED_OUTPUT_TERMS:
            if term.lower() in text:
                raise ValueError(f"{path} contains final-readiness banned term: {term}")


def validate_all(data_dir: Path, outputs_dir: Path, *, require_outputs: bool, require_realtime: bool) -> None:
    validate_inputs(data_dir, require_realtime=require_realtime)
    if require_outputs:
        validate_outputs(outputs_dir, require_realtime=require_realtime)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate NLP term project JSON contracts.")
    parser.add_argument("--check-all", action="store_true", help="Validate known input/output files.")
    parser.add_argument("--inputs-only", action="store_true", help="Only validate required input fixtures.")
    parser.add_argument("--seed-data", action="store_true", help="Validate generated seed datasets.")
    parser.add_argument("--source-probe", type=Path, help="Validate source probe metadata.")
    parser.add_argument("--knowledge-provenance", type=Path, help="Validate knowledge docs against source probe metadata.")
    parser.add_argument("--require-official-chain", action="store_true", help="Require provenance sources to be official-chain verified.")
    parser.add_argument("--model-shortlist", type=Path, help="Validate model shortlist metadata.")
    parser.add_argument("--final-readiness", action="store_true", help="Reject placeholder terms in final-facing outputs.")
    parser.add_argument("--require-raw-files", action="store_true", help="Require source probe raw files to exist.")
    parser.add_argument("--require-realtime", action="store_true", help="Require realtime input/output files.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--outputs-dir", type=Path, default=Path("outputs"))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if (
        not args.check_all
        and not args.inputs_only
        and not args.seed_data
        and not args.source_probe
        and not args.knowledge_provenance
        and not args.model_shortlist
        and not args.final_readiness
    ):
        parser.error("at least one validation mode is required")
    try:
        if args.inputs_only:
            validate_inputs(args.data_dir, require_realtime=args.require_realtime)
        if args.check_all:
            validate_all(
                args.data_dir,
                args.outputs_dir,
                require_outputs=True,
                require_realtime=args.require_realtime,
            )
        if args.seed_data:
            validate_seed_data(args.data_dir)
        if args.source_probe:
            validate_source_probe(args.source_probe, require_raw_files=args.require_raw_files)
        if args.knowledge_provenance:
            validate_knowledge_provenance(
                args.data_dir,
                args.knowledge_provenance,
                require_official_chain=args.require_official_chain,
            )
        if args.model_shortlist:
            validate_model_shortlist(args.model_shortlist)
        if args.final_readiness:
            validate_final_readiness(args.outputs_dir)
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        raise SystemExit(f"validation failed: {exc}") from exc
    print("validation-ok")


if __name__ == "__main__":
    main()
