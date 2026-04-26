from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "artifacts"
OUTPUT_DIR.mkdir(exist_ok=True)

TARGET_SUFFIXES = {".py", ".html", ".css", ".md", ".txt"}
EXCLUDE_PARTS = {".venv", "__pycache__", "instance", "artifacts"}


def should_include(path: Path) -> bool:
    return path.suffix in TARGET_SUFFIXES and not any(part in EXCLUDE_PARTS for part in path.parts)


def main():
    output_path = OUTPUT_DIR / "source_submission_full.txt"
    with output_path.open("w", encoding="utf-8") as handle:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and should_include(path):
                rel = path.relative_to(ROOT)
                handle.write("=" * 90 + "\n")
                handle.write(f"FILE: {rel}\n")
                handle.write("=" * 90 + "\n")
                with path.open("r", encoding="utf-8", errors="ignore") as src:
                    for idx, line in enumerate(src, start=1):
                        handle.write(f"{idx:04d}: {line}")
                handle.write("\n\n")
    print(f"生成完成: {output_path}")


if __name__ == "__main__":
    main()
