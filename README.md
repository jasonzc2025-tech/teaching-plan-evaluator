# 住培临床教案质量智能评审系统 V1.0

这是一个基于 Flask 的 Web 应用，用于对住院医师规范化培训相关教案进行结构化评审、问题归类和研究型统计分析。

## 核心能力

- 教案文本上传与粘贴评审
- 五类教案自动识别或手动指定
- 结构化输出：总分、条款分、问题列表、优点、修改建议
- 研究型落库：问题分类、严重程度、条款失分、版本信息
- 后台分析：类型分布、问题热度、严重程度、近14天趋势
- CSV 导出：记录表、问题表、条款表
- 软著辅助脚本：自动生成源程序交存版文本

## 目录说明

```text
.
├── app.py                     # 启动入口
├── wsgi.py                    # 生产环境入口
├── config.py                  # 配置对象
├── requirements.txt
├── scripts/
│   └── build_source_submission.py
├── teaching_eval/
│   ├── __init__.py
│   ├── db.py
│   ├── schema.py
│   ├── prompts.py
│   ├── extractors.py
│   ├── parser.py
│   ├── llm_client.py
│   ├── repository.py
│   ├── stats.py
│   ├── services.py
│   ├── routes_public.py
│   └── routes_admin.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── admin_dashboard.html
│   └── record_detail.html
└── static/
    └── app.css
```

## 快速启动

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，然后填写：

- `LLM_API_KEY`
- `LLM_API_BASE`
- `LLM_MODEL_NAME`
- `SECRET_KEY`
- `ADMIN_PASSWORD`

### 3. 启动应用

```bash
python app.py
```

访问：

- 前台：`http://127.0.0.1:5000/`
- 后台：`http://127.0.0.1:5000/admin`

### PDF 解析（本地非 Docker）

上传 `.pdf` 时，服务端会调用 `pdftotext`（来自 **Poppler**，包名常见为 `poppler-utils`）。Docker 镜像已安装；若在 Windows 或未装 Poppler 的环境直接 `python app.py`，需自行安装并保证 `pdftotext` 在 `PATH` 中，否则 PDF 会解析失败。

### 排障时查看接口错误详情

`.env` 中设置 `EVAL_EXPOSE_INTERNAL_ERRORS=true` 后，非预期异常会在接口中返回具体原因（**勿在生产对公网开启**）。用户输入类错误（如格式不支持、内容过短）始终返回明确文案。

## 与旧版兼容

本版本保留了以下接口，便于替换旧系统：

- `POST /evaluate`
- `GET /health`
- `GET|POST /admin/login`
- `GET /admin`
- `GET /admin/record/<record_id>`

## 研究型数据结构

### records 主表
记录单份教案评审的总体信息、版本信息和摘要结果。

### record_issues 问题表
按问题粒度保存每条问题的分类、严重程度、证据位置和建议。

### clause_scores 条款表
按条款保存满分、实得分、判定说明和证据位置。

## 软著辅助

执行以下脚本可生成源程序交存文本：

```bash
python scripts/build_source_submission.py
```

输出文件位于 `artifacts/source_submission_full.txt`。代码变更后应重新执行该脚本，避免交存文本与仓库不一致。

部署或打压缩包前，可在项目根目录一键执行（清理缓存并再生成交存文本）：

```bash
python scripts/prepare_deploy.py
```

## 打包发布前（可选）

亦可仅用 PowerShell 手动清理：

```powershell
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
```

## 注意事项

- 系统默认不落库教案原文，只记录摘要和结构化评审结果。
- 如需做前后对比研究，建议在前台补录“科室、带教老师、课程名称、轮次”等字段。
- 建议部署时使用 Gunicorn / uWSGI + Nginx。
