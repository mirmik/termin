#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


def write_compilation_database(
    directory: Path,
    compiler: Path,
    sources: list[Path],
) -> None:
    commands = [
        {
            "directory": str(source.parent),
            "file": str(source),
            "arguments": [
                str(compiler),
                "-std=c++20",
                "-fsyntax-only",
                str(source),
            ],
        }
        for source in sources
    ]
    (directory / "compile_commands.json").write_text(
        json.dumps(commands, indent=2),
        encoding="utf-8",
    )


def run_checker(
    checker: Path,
    database: Path,
    fixtures: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(checker),
            "-p",
            str(database),
            "--repo-root",
            str(fixtures),
            "--format",
            "jsonl",
            *arguments,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def parse_jsonl(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    checker = Path(sys.argv[1]).resolve()
    compiler = Path(sys.argv[2]).resolve()
    fixtures = Path(sys.argv[3]).resolve()
    clean_source = fixtures / "clean.cpp"
    violation_source = fixtures / "violations.cpp"
    consumer_source = fixtures / "consumer.cpp"
    consumer_header = fixtures / "owned_headers" / "consumer_only_violation.hpp"
    require(consumer_header.is_file(), f"missing fixture header: {consumer_header}")

    with tempfile.TemporaryDirectory(prefix="termin-cpp-class-layout-") as temp:
        database = Path(temp)

        write_compilation_database(database, compiler, [clean_source])
        clean = run_checker(checker, database, fixtures)
        require(clean.returncode == 0, f"clean fixture failed:\n{clean.stderr}")
        require(parse_jsonl(clean.stdout) == [], "clean fixture produced violations")

        write_compilation_database(database, compiler, [violation_source])
        violations = run_checker(checker, database, fixtures)
        require(violations.returncode == 1, "violating fixture did not fail")

        records = parse_jsonl(violations.stdout)
        records_by_class = {record["class"]: record for record in records}
        expected_classes = {
            "FieldsAtBottom",
            "FieldAfterConstructor",
            "FieldAfterFunctionTemplate",
            "AccessSectionDoesNotResetOrder",
            "AnonymousUnionAfterMethod",
            "FieldAtBottomInTemplate",
            "MacroFieldAfterMethod",
        }
        require(
            set(records_by_class) == expected_classes,
            f"unexpected classes: {set(records_by_class)}",
        )

        fields_at_bottom = records_by_class["FieldsAtBottom"]["misplaced_fields"]
        field_names = {field["name"] for field in fields_at_bottom}
        require(
            field_names == {"value_", "revision_"},
            f"unexpected field list: {field_names}",
        )

        macro_fields = records_by_class["MacroFieldAfterMethod"]["misplaced_fields"]
        require(len(macro_fields) == 1, "macro fixture produced an unexpected field count")
        require(
            macro_fields[0]["macro_expansion"] is True,
            "macro field was not marked as a macro expansion",
        )

        no_fail_result = run_checker(checker, database, fixtures, "--no-fail")
        require(no_fail_result.returncode == 0, "--no-fail did not suppress exit 1")

        filtered_result = run_checker(
            checker,
            database,
            fixtures,
            "--path",
            "clean.cpp",
        )
        require(filtered_result.returncode == 0, "path filter did not filter violations")
        require(parse_jsonl(filtered_result.stdout) == [], "path filter leaked violations")

        write_compilation_database(database, compiler, [consumer_source])
        consumer_header_result = run_checker(
            checker,
            database,
            fixtures,
            "--path",
            "owned_headers",
        )
        require(
            consumer_header_result.returncode == 1,
            "path filter missed a header reached through an outside consumer TU\n"
            f"return code: {consumer_header_result.returncode}\n"
            f"stdout:\n{consumer_header_result.stdout}\n"
            f"stderr:\n{consumer_header_result.stderr}",
        )
        consumer_records = parse_jsonl(consumer_header_result.stdout)
        require(
            [record["class"] for record in consumer_records]
            == ["ConsumerOnlyViolation"],
            f"unexpected consumer-header records: {consumer_records}",
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
