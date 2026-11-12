"""Candidate research conditions, not professional approval or an ability score."""
VERSION = "research.foundation-1.0.0"
METHODS = {
    "undecided": "先明确问题，再选择适合的研究方法。",
    "empirical": "说明观察对象、比较条件、测量方式和替代解释。",
    "qualitative": "保留参与者情境、取样说明、原始片段、反例和研究者反思。",
    "humanities": "核对材料出处与语境，说明解释路径和其他合理解读。",
    "design": "明确使用目标，通过原型、使用反馈和修改记录比较方案。",
    "simulation": "明确模型机制、参数来源和适用范围，再用现实观察核对。",
}

def assess_problem(value, method):
    missing = [label for field, label in [("context", "问题发生的情境"), ("goal", "什么变化才有意义"),
                                          ("constraints", "时间、资料或资源限制")]
               if not value.get(field, "").strip()]
    return {"policy_version": VERSION, "method": method, "guidance": METHODS[method],
            "missing": missing, "domain_review": "not_reviewed",
            "scope": "问题记录的条件检查，不证明问题已解决或研究方法有效"}

def record_checks(value):
    return {"policy_version": VERSION, "provenance": value.get("provenance", "reported"),
            "provenance_is_author_declaration": True, "domain_review": "not_reviewed",
            "assistance": value.get("assistance", "") or "未记录",
            "ability_judgment": "not_assessed"}

def describe():
    return {"version": VERSION, "methods": METHODS,
            "conditions": ["问题与目标", "情境与约束", "来源与版本", "观察与解释分列", "帮助与反思"],
            "domain_review": "not_reviewed",
            "skills": {"state": "curated_workflow_rules", "note": "v1保留基础研究记录；v2提供资料、方向、实验、模拟和成果能力。执行环境与领域质量分别核对。"}}
