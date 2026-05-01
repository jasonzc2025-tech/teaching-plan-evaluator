import re
from typing import Dict, Iterable, List


COMMON_RULES = [
    {
        "code": "objectives",
        "title": "教学目标",
        "severity": "important",
        "keywords": ["教学目标", "知识目标", "技能目标", "能力目标", "临床思维目标", "职业素养目标"],
        "suggestion": "补充知识、技能/能力、临床思维或职业素养等可观察、可评价的教学目标。",
    },
    {
        "code": "process",
        "title": "教学流程",
        "severity": "important",
        "keywords": ["教学流程", "教学过程", "流程安排", "时间分配", "实施步骤", "教学步骤"],
        "suggestion": "写清导入、学员参与、教师引导、总结反馈等主要流程。",
    },
    {
        "code": "resident_participation",
        "title": "住培医师参与",
        "severity": "important",
        "keywords": ["住培医师", "规培医师", "学员", "学生", "汇报", "讨论", "练习", "操作"],
        "suggestion": "明确住培医师在活动中的任务，例如汇报、分析、操作、讨论或反馈。",
    },
    {
        "code": "evaluation_feedback",
        "title": "评价与反馈",
        "severity": "important",
        "keywords": ["评价", "评估", "考核", "反馈", "提问", "观察", "评分", "课后反馈"],
        "suggestion": "补充过程性评价、提问/观察、操作考核或课后反馈方式。",
    },
    {
        "code": "safety_ethics",
        "title": "安全与伦理",
        "severity": "important",
        "keywords": ["知情同意", "隐私", "脱敏", "患者安全", "风险", "应急", "安全", "保护"],
        "suggestion": "补充患者知情同意、隐私保护、资料脱敏、风险控制或应急预案。",
    },
]


TYPE_RULES = {
    "教学查房": [
        {
            "code": "round_case",
            "title": "病例与查房场景",
            "severity": "suggestion",
            "keywords": ["病例", "查房", "床旁", "体格检查", "阳性体征", "鉴别诊断"],
            "suggestion": "补充病例摘要、床旁查房安排、体格检查示范或鉴别诊断讨论。",
        }
    ],
    "病例讨论": [
        {
            "code": "discussion_question_chain",
            "title": "讨论问题链",
            "severity": "suggestion",
            "keywords": ["讨论问题", "问题链", "鉴别诊断", "诊疗决策", "小组讨论", "病例摘要"],
            "suggestion": "设置病例讨论的问题链，体现诊断、鉴别诊断和治疗决策过程。",
        }
    ],
    "临床小讲课": [
        {
            "code": "lecture_design",
            "title": "小讲课重点难点与互动",
            "severity": "suggestion",
            "keywords": ["重点", "难点", "导入", "互动", "提问", "指南", "参考文献"],
            "suggestion": "补充重点难点、病例或问题导入、互动提问和指南/参考依据。",
        }
    ],
    "技能培训": [
        {
            "code": "skill_safety_steps",
            "title": "技能步骤与安全规范",
            "severity": "suggestion",
            "keywords": ["操作", "示范", "练习", "无菌", "适应证", "禁忌证", "并发症", "应急预案"],
            "suggestion": "补充操作步骤、教师示范、学员练习、无菌要求和并发症/应急处理。",
        }
    ],
    "教学门诊": [
        {
            "code": "clinic_workflow",
            "title": "门诊教学流程",
            "severity": "suggestion",
            "keywords": ["门诊", "问诊", "查体", "医患沟通", "briefing", "debriefing", "隐私", "诊疗安全"],
            "suggestion": "补充门诊前后 briefing/debriefing、问诊查体任务、教师观察反馈和隐私保护。",
        }
    ],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _contains_any(normalized_text: str, keywords: Iterable[str]) -> bool:
    return any((keyword or "").lower().replace(" ", "") in normalized_text for keyword in keywords)


def run_precheck(text_content: str, metadata: Dict) -> Dict:
    declared_type = (metadata.get("declared_type") or "").strip()
    normalized_text = _normalize(text_content)
    rules: List[Dict] = COMMON_RULES + TYPE_RULES.get(declared_type, [])
    checks = []

    for rule in rules:
        found = _contains_any(normalized_text, rule["keywords"])
        checks.append({
            "code": rule["code"],
            "title": rule["title"],
            "status": "found" if found else "missing",
            "severity": rule["severity"],
            "suggestion": rule["suggestion"],
            "keywords": rule["keywords"],
        })

    missing = [item for item in checks if item["status"] == "missing"]
    important_missing = [item for item in missing if item["severity"] == "important"]
    return {
        "doc_type": declared_type,
        "char_count": len(text_content or ""),
        "checks": checks,
        "missing_count": len(missing),
        "important_missing_count": len(important_missing),
        "can_continue": True,
        "message": "提交前自查仅作快速缺项提示，不替代完整 AI 评审。",
    }
