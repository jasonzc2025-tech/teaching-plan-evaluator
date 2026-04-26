# 住培临床教案质量智能评审系统 V3.0

> 基于大语言模型 · 条款级 · 证据驱动 · 可复核

本系统面向住院医师规范化培训（住培）场景，对五类教案进行结构化、百分制、条款级评审，支持网页端实时使用与质控管理后台统计分析。

## 功能特性

- **五类教案支持**：教学查房、病例讨论、临床小讲课、技能培训、教学门诊
- **百分制条款评分**：通用维度（45分）+ 分项维度（55分），每分有证据依据
- **流式实时输出**：LLM 生成过程实时展示，无需等待
- **自动元数据解析**：从文件名自动识别科室、带教老师、课程名称
- **否决项刚性约束**：知情同意、应急预案等关键安全条款缺失自动触发否决
- **防操纵机制**：检测并过滤教案中植入的诱导性评分指令
- **研究型后台**：按老师/科室/评审轮次多维统计，支持 CSV 导出
- **多轮评审追踪**：同一课程多次提交自动记录进步轨迹

## 快速开始

### 方式一：直接访问网页端

无需注册，上传教案文件（.docx / .pdf / .txt）或粘贴文本即可评审。

### 方式二：本地部署（Python venv）

    git clone https://github.com/jasonzc2025-tech/teaching-plan-evaluator.git
    cd teaching-plan-evaluator
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install "gunicorn>=21.2" "gevent>=23.9"
    cp .env.example .env
    # 编辑 .env，填入 LLM_API_KEY、SECRET_KEY、ADMIN_PASSWORD
    gunicorn -w 2 -k gevent -b 0.0.0.0:8081 --timeout 300 wsgi:application

## 环境变量说明

| 变量 | 说明 | 示例 |
|---|---|---|
| LLM_API_KEY | DeepSeek API 密钥 | sk-xxx |
| LLM_API_BASE | API 地址 | https://api.deepseek.com/v1/chat/completions |
| LLM_MODEL_NAME | 模型名称 | deepseek-chat |
| SECRET_KEY | Flask session 密钥 | 随机长串 |
| ADMIN_PASSWORD | 后台登录密码 | 自定义 |
| DB_PATH | SQLite 数据库路径 | /app/instance/eval_records.db |

## 目录结构

    .
    ├── app.py                  # 开发启动入口
    ├── wsgi.py                 # 生产环境入口
    ├── config.py               # 配置管理
    ├── requirements.txt        # 依赖列表
    ├── teaching_eval/          # 核心业务模块
    │   ├── routes_public.py    # 公开路由（评审接口）
    │   ├── routes_admin.py     # 后台路由
    │   ├── services.py         # 业务逻辑
    │   ├── llm_client.py       # LLM 客户端（支持流式）
    │   ├── extractors.py       # 文件文本提取
    │   ├── parser.py           # 结构化结果解析
    │   ├── repository.py       # 数据库操作
    │   ├── prompts.py          # 提示词加载
    │   └── prompt_blocks/      # 模块化提示词文件
    ├── templates/              # Jinja2 模板
    ├── static/                 # 静态资源
    └── nginx/                  # Nginx 配置

## Skill 使用

本项目提供 Claude Skill 文件，供质控管理人员在 Claude 中本地装载，实现教案批量初筛。

详见 references/SKILL.md

## 版本历史

| 版本 | 日期 | 主要变更 |
|---|---|---|
| V3.0 | 2026-04 | 流式输出、UI重设计、自动元数据、后台多维统计、评审轮次追踪 |
| V2.6 | 2026-03 | 百分制条款评分、五类教案、三联证据、否决项、防操纵机制 |
| V1.0 | 2026-01 | 提示词体系构建，以 Skill 形式发布，支持主流大语言模型平台加载使用 |

## 申报信息

本系统已参加中国高等教育学会全国医学教育发展中心医学教育智能体及应用案例申报（2026年4月），申报单位：上海市同仁医院。

## 许可证

MIT License © 2026 张畅 · 上海市同仁医院
