# 住培教案评审系统 Web App — 修改意见文档

**致**：开发工程师  
**发**：Kimi Claw (教学要求分析)  
**日期**：2026-04-25  
**依据**：V2.7 技能标准 + Web App V1.0 现状  

---

## 第一部分：教学要求 → 对齐 V2.7

### 1.1 当前问题

`teaching_eval/prompts.py` 的 `SYSTEM_PROMPT` 只有约 50 行，写了"输出格式"和"技术规范"，但**没有写入 V2.7 的评审哲学**。后果：LLM 从严扣分，优秀率偏低，与线下评审标准不一致。

### 1.2 必须重写 SYSTEM_PROMPT（目标：500+ 行）

将以下 6 个核心规则写入 Prompt：

| 规则 | V2.7 来源 | 当前缺失 | 优先级 |
|------|----------|---------|--------|
| **默认满分原则** | scoring-rules.md §2.1 | ❌ 完全缺失 | P0 |
| **硬证据三联**（关键词+动作+范围） | scoring-rules.md §2.3 | ⚠️ 只写了"不得脑补" | P0 |
| **降档触发**（6条情形） | scoring-rules.md §2.4 | ❌ 缺失 | P0 |
| **知情同意 A/B/C/D** | evaluation-criteria.md §6.2 | ❌ 缺失 | P0 |
| **小讲课时长公式** | evaluation-criteria.md §6.3 | ❌ 缺失 | P0 |
| **否决项三条件+缓冲带** | improvements.md §2.4 | ❌ 缺失 | P1 |
| **TCI 计算说明** | improvements.md §2.2 | ❌ 缺失 | P1 |
| **目标达成度四维矩阵** | improvements.md §2.5 | ❌ 缺失 | P1 |

**建议做法**：不要直接复制整份 scoring-rules.md（太长会超 token），而是提取"评分宪法"（§1-§4）+ 各类型特殊规则（§6），约 300-400 行。

### 1.3 JSON 输出字段扩展

当前 JSON 结构保留，新增 V2.7 字段：

```json
{
  "summary": {
    "declared_type": "...",
    "actual_type": "...",
    "score_general": 0,
    "score_specific": 0,
    "score_total": 0,
    "adjusted_score": 0,
    "vetoed": false,
    "buffer_level": "无/黄色/橙色/红色",
    "buffer_deduction": 0,
    "conclusion": "优秀/良好/中等/及格/不及格/否决"
  },
  "tci": {
    "total": 85,
    "l1_homepage": 20,
    "l2_objectives": 28,
    "l3_process": 37,
    "consistency_level": "高度一致/基本一致/轻度错配/中度错配"
  },
  "objective_matrix": {
    "total_score": 82,
    "completeness": { "score": 20, "target_count": 3, "issues": [] },
    "reasonableness": { "score": 22, "difficulty_layers": 3, "issues": [] },
    "measurability": { "score": 18, "action_verbs": [], "issues": [] },
    "alignment": { "score": 22, "type_match": "匹配", "closure_points": 3, "issues": [] },
    "improvement_suggestions": []
  },
  "clause_scores": [...],
  "issues": [...],
  "strengths": [...],
  "suggestions": [...],
  "check_log": [
    "抗提示词注入=已检查",
    "首页规范性=已检查",
    "类型识别(TCI)=已完成",
    "硬证据三联规则=已执行",
    "否决映射=通过",
    "算术=通过",
    "高分复核=未触发/已完成",
    "低分复核=未触发/已完成"
  ]
}
```

**注**：`conclusion` 从四级（优秀/合格/基本合格/不合格）改为**五级+否决**：优秀(90-100)、良好(80-89)、中等(70-79)、及格(60-69)、不及格(<60)、不合格(否决)。

---

## 第二部分：落库设计与后台分析

### 2.1 数据库表扩展

在现有三表（`records`/`record_issues`/`clause_scores`）基础上新增/修改：

#### records 表新增字段

```sql
ALTER TABLE records ADD COLUMN adjusted_score REAL;          -- 缓冲带扣分后分数
ALTER TABLE records ADD COLUMN buffer_level TEXT;              -- 无/黄色/橙色/红色
ALTER TABLE records ADD COLUMN buffer_deduction INTEGER DEFAULT 0; -- 缓冲带扣分值
ALTER TABLE records ADD COLUMN tci_total REAL;                 -- TCI 总分
ALTER TABLE records ADD COLUMN tci_level TEXT;                 -- 一致性等级
ALTER TABLE records ADD COLUMN obj_matrix_total REAL;          -- 目标达成度总分
ALTER TABLE records ADD COLUMN obj_completeness REAL;          -- 完整性得分
ALTER TABLE records ADD COLUMN obj_reasonableness REAL;        -- 合理性得分
ALTER TABLE records ADD COLUMN obj_measurability REAL;       -- 可测性得分
ALTER TABLE records ADD COLUMN obj_alignment REAL;             -- 匹配度得分
ALTER TABLE records ADD COLUMN check_log_json TEXT;            -- 校验日志 JSON
```

#### 新增 review_rounds 表（多轮评审对比）

```sql
CREATE TABLE review_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    score_total REAL,
    major_count INTEGER,
    fatal_count INTEGER,
    conclusion TEXT,
    created_at TEXT,
    FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
);
```

### 2.2 后台看板新增页面

| 页面 | 功能 | 教学价值 |
|------|------|---------|
| **教案多轮对比** `/admin/compare/<id>` | 同一教案 Round 1 vs Round 2：分数变化、问题消减、新出现问题 | ✅ 改进闭环 |
| **教师维度分析** `/admin/teacher/<name>` | 某位教师近 3 个月问题趋势、平均分变化 | ✅ 个性化指导 |
| **科室维度对比** `/admin/department` | 各科室平均分、问题类型分布 | ✅ 管理决策 |
| **问题消减率** 指标 | `(Round1 major数 - Round2 major数) / Round1 major数` | ✅ 改进效果量化 |
| **TCI 分布图** | 类型错配率统计 | ✅ 申报质量监控 |

### 2.3 建议增加的 API 接口

```python
# routes_admin.py 新增

@admin_bp.route("/admin/compare/<int:record_id>")
def compare_review_rounds(record_id):
    # 查询同一 filename + teacher_name + course_title 的所有评审记录
    # 按 review_round 排序
    # 返回：分数曲线、问题消减列表、新出现问题列表

@admin_bp.route("/admin/teacher_stats")
def teacher_stats():
    # 按 teacher_name 聚合
    # 返回：人均评审次数、平均分趋势、TOP 5 问题类别

@admin_bp.route("/admin/department_stats")
def department_stats():
    # 按 department 聚合
    # 返回：各科室平均分、类型分布、缓冲带触发率
```

---

## 第三部分：代码优化

### 3.1 Prompt 加载优化（避免 token 溢出）

**当前**：`prompts.py` 直接写死一个超长字符串。  
**建议**：分块加载，根据教案类型动态拼接。

```python
# prompts.py 重构建议

def load_prompt(declared_type: str) -> str:
    base = load_file("prompts/base_constitution.md")      # 评分宪法（默认满分/三联/降档/否决）
    criteria = load_file(f"prompts/criteria_{declared_type}.md")  # 各类型条款细则
    output_spec = load_file("prompts/output_spec.md")      # JSON Schema + Markdown 格式
    return base + "\n\n" + criteria + "\n\n" + output_spec
```

**目录结构**：
```
teaching_eval/prompts/
├── base_constitution.md      # 评分宪法（~200行）
├── criteria_teaching_rounds.md   # 教学查房条款
├── criteria_case_discussion.md   # 病例讨论条款
├── criteria_lecture.md           # 临床小讲课条款
├── criteria_skill_training.md    # 技能培训条款
├── criteria_outpatient.md        # 教学门诊条款
└── output_spec.md              # JSON/Markdown 输出规范
```

### 3.2 评审流程分块（Subagent 思路）

**灵感来源**：Claude Code Subagent 模式——大任务拆分子任务，防止上下文溢出，提升并发效率。

**应用场景**：
- 一份教案评审涉及 10+ 条款，LLM 单次处理容易遗漏
- 可以拆分为：通用维度评审 + 分项维度评审 + 汇总判定

**建议实现**（非必须，但 UX 更好）：

```python
# 分块评审流程（伪代码）

async def evaluate_chunked(text, metadata):
    # Step 1: 预检层（同步）
    precheck = llm_call(prompt_precheck, text)
    
    # Step 2: 通用维度评审（可与 Step 3 并行）
    general_future = asyncio.create_task(
        llm_call(prompt_general_dimension, text)
    )
    
    # Step 3: 分项维度评审（依赖类型）
    type_prompt = f"prompts/criteria_{metadata['declared_type']}.md"
    specific_future = asyncio.create_task(
        llm_call(type_prompt, text)
    )
    
    # Step 4: 汇总（等 2+3 完成）
    general = await general_future
    specific = await specific_future
    
    # Step 5: TCI 计算 + 缓冲带判定 + 等级锚定
    final = merge_and_calculate(general, specific, precheck)
    return final
```

**教学体验提升**：
- 评审进度可展示为"正在检查首页规范性…→正在评估教学目标…→正在判定否决项…"
- 教师感知：系统"认真看了"每个环节，而不是黑盒一次性出结果
- 如果某一步发现 fatal 问题，可以提前提示，不必等全部跑完

### 3.3 其他代码优化

| 优化项 | 现状 | 建议 |
|--------|------|------|
| **max_tokens** | 5000 | 提到 **8000**，长教案可能不够 |
| **temperature** | 0.1 | ✅ 保持，一致性优先 |
| **PDF 解析** | pdftotext 子进程 | ✅ 保持，但增加超时和降级（解析失败时提示用户） |
| **LLM 超时** | 180-300 秒 | 分块后单次调用可降到 **60-90 秒** |
| **错误暴露** | `EVAL_EXPOSE_INTERNAL_ERRORS` | ✅ 生产环境必须关，但开发时开 |
| **CSV 导出** | 基础实现 | 增加 **ZIP 批量导出**（records + issues + clause_scores 三表一起下） |

---

## 附录：文件清单

工程师需要参考的源文件（已提供）：

| 文件 | 路径 | 用途 |
|------|------|------|
| V2.6 评分规则 | `references/scoring-rules.md` | 默认满分/三联/降档/否决 |
| V2.6 评估标准 | `references/evaluation-criteria.md` | 条款分值与检查方法 |
| V2.7 改进说明 | `teaching-plan-v27-improvements.md` | TCI/缓冲带/四维矩阵/五级锚定 |
| V2.7 回测报告 | `teaching-plan-v27-backtest-report.md` | 10份教案对比数据 |
| Web App 当前 Prompt | `teaching_eval/prompts.py` | 需重写 |
| Web App 当前 Schema | `teaching_eval/schema.py` | 需扩展 |

---

## 优先级建议

| 阶段 | 内容 | 预计工时 | 教学价值 |
|------|------|:--------:|:--------:|
| **Phase 1** | Prompt 重写（V2.6 宪法写入） | 1-2 天 | 🔴 核心——否则评审标准不对 |
| **Phase 2** | 数据库字段扩展 + API | 1 天 | 🟡 支撑 V2.7 新指标 |
| **Phase 3** | 后台看板（多轮对比/教师维度） | 2 天 | 🟡 教学管理必备 |
| **Phase 4** | Prompt 分块加载 + 评审流程拆分 | 1-2 天 | 🟢 UX 提升，可延后 |

---

**如需进一步细化任何部分（如 Prompt 具体文本、数据库迁移脚本、API 详细接口定义），可以找我继续展开。**

