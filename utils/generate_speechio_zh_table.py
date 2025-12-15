#!/usr/bin/env python3
import csv
import pathlib
import re
from typing import Dict, List, Optional


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
README_PATH = PROJECT_ROOT / "README.md"
RESULTS_ROOT = PROJECT_ROOT / "results"
OUTPUT_PATH = RESULTS_ROOT / "speechio_zh_datasets_with_wer.tsv"


def parse_speechio_zh_datasets(readme_path: pathlib.Path) -> List[Dict[str, str]]:
    datasets: List[Dict[str, str]] = []

    with readme_path.open("r", encoding="utf-8") as f:
        for line in f:
            if "SPEECHIO_ASR_ZH" not in line:
                continue

            if "&check;" not in line:
                continue

            stripped = line.strip().strip("|")
            cells = [cell.strip() for cell in stripped.split("|") if cell.strip()]

            dataset_id: Optional[str] = None
            dataset_index: Optional[int] = None

            for index, cell in enumerate(cells):
                if cell.startswith("SPEECHIO_ASR_ZH"):
                    dataset_id = cell
                    dataset_index = index
                    break

            if dataset_id is None or dataset_index is None:
                continue

            try:
                numeric_suffix = int(dataset_id[-5:])
            except ValueError:
                continue

            if numeric_suffix < 1 or numeric_suffix > 26:
                continue

            try:
                name = cells[dataset_index + 1]
                scenario = cells[dataset_index + 2].replace("<br>", "/")
                topic = cells[dataset_index + 3].replace("<br>", "/")
                duration_hours = cells[dataset_index + 4]
                difficulty = cells[dataset_index + 5]
            except IndexError:
                continue

            datasets.append(
                {
                    "dataset_id": dataset_id,
                    "name": name,
                    "scenario": scenario,
                    "topic": topic,
                    "duration_hours": duration_hours,
                    "difficulty": difficulty,
                }
            )

    return datasets


WER_PATTERN = re.compile(r"%WER\s+([0-9]+(?:\.[0-9]+)?)")


def extract_wer_from_results(results_path: pathlib.Path) -> Optional[float]:
    try:
        with results_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None

    if len(lines) < 2:
        return None

    match = WER_PATTERN.search(lines[1])
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def find_best_wer_for_dataset(results_root: pathlib.Path, dataset_id: str) -> Optional[float]:
    pattern = f"*{dataset_id}*"
    best_wer: Optional[float] = None

    for dir_path in results_root.glob(f"**/{pattern}"):
        if not dir_path.is_dir():
            continue

        results_txt = dir_path / "RESULTS.txt"
        wer = extract_wer_from_results(results_txt)

        if wer is None:
            continue

        if best_wer is None or wer < best_wer:
            best_wer = wer

    return best_wer


def main() -> None:
    datasets = parse_speechio_zh_datasets(README_PATH)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "dataset_id",
                "name",
                "scenario",
                "topic",
                "duration_hours",
                "difficulty",
                "wer",
            ]
        )

        for dataset in datasets:
            dataset_id = dataset["dataset_id"]
            wer = find_best_wer_for_dataset(RESULTS_ROOT, dataset_id)

            writer.writerow(
                [
                    dataset_id,
                    dataset["name"],
                    dataset["scenario"],
                    dataset["topic"],
                    dataset["duration_hours"],
                    dataset["difficulty"],
                    "" if wer is None else f"{wer:.2f}",
                ]
            )


if __name__ == "__main__":
    main()
