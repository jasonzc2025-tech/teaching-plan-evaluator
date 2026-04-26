from collections import Counter, defaultdict
from typing import Dict, List


def summarize_issue_matrix(issues: List[Dict]) -> Dict:
    category_counter = Counter()
    severity_counter = Counter()
    cross = defaultdict(Counter)

    for item in issues:
        category = item.get("issue_category", "未分类")
        severity = item.get("severity", "minor")
        category_counter[category] += 1
        severity_counter[severity] += 1
        cross[category][severity] += 1

    return {
        "category_counter": category_counter,
        "severity_counter": severity_counter,
        "cross": cross,
    }
