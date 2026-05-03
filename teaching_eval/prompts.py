from pathlib import Path


PROMPT_VERSION = "prompt-v3.2"
PROMPT_BLOCKS_DIR = Path(__file__).resolve().parent / "prompt_blocks"

TYPE_TO_BLOCK = {
    "教学查房": "criteria_teaching_rounds.md",
    "病例讨论": "criteria_case_discussion.md",
    "临床小讲课": "criteria_lecture.md",
    "技能培训": "criteria_skill_training.md",
    "教学门诊": "criteria_outpatient.md",
}


def _read_block(filename: str) -> str:
    path = PROMPT_BLOCKS_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_system_prompt(declared_type: str) -> str:
    base = _read_block("base_constitution.md")
    output_spec = _read_block("output_spec.md")
    if declared_type in TYPE_TO_BLOCK:
        criteria_blocks = [_read_block(TYPE_TO_BLOCK[declared_type])]
    else:
        criteria_blocks = [_read_block("criteria_general.md")]
        criteria_blocks.extend(_read_block(filename) for filename in TYPE_TO_BLOCK.values())
    parts = [part for part in (base, *criteria_blocks, output_spec) if part]
    return "\n\n".join(parts)
