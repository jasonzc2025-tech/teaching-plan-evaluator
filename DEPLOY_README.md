# 路线A Docker 部署说明

## 适用场景
- 继续使用阿里云 ECS
- 不再依赖宝塔里的旧 Python 运行环境
- 先保留 SQLite 与本地文件
- 浏览器访问的 **Web 应用**；对外测试入口为 **8081**（经 Nginx），与旧站端口可并存

## 部署前检查（上传服务器 / 打压缩包前）
1. 已复制 `.env.example` → `.env`，并填写：`SECRET_KEY`、`ADMIN_PASSWORD`、`LLM_API_KEY`（及按需的 `LLM_API_BASE`、`LLM_MODEL_NAME`）。
2. 生产环境保持 `EVAL_EXPOSE_INTERNAL_ERRORS=false`（勿对公网暴露内部异常）。
3. 若需提交软著源程序合订本，在仓库根目录执行：  
   `python scripts/prepare_deploy.py`  
   （会清理 `__pycache__`、`.pyc` 并重新生成 `artifacts/source_submission_full.txt`。）
4. 确认存在 `static/vendor/chart.umd.min.js`（后台图表用，不依赖外网 CDN）。
5. 安全组：建议仅放行 **8081**；`5001` 仅绑定本机时外网无法访问属正常。

## 目录说明
- `Dockerfile`：应用镜像构建文件
- `docker-compose.yml`：一键启动 Web + Nginx
- `nginx/default.conf`：反向代理配置
- `.env.example`：环境变量模板
- `instance/`：SQLite 数据库持久化目录
- `data/uploads/`：预留上传文件持久化目录

## 服务器准备
### Ubuntu/Debian
按 Docker 官方文档，推荐通过 Docker 的 apt 仓库安装 Docker Engine。 

### CentOS Stream 9/10
按 Docker 官方文档，推荐通过 Docker 的 rpm 仓库安装 Docker Engine。 

## 部署步骤
1. 把整个目录上传到 ECS，例如 `/opt/teaching-plan-evaluator-webapp`。
2. 复制 `.env.example` 为 `.env`，至少改这些值：
   - `SECRET_KEY`
   - `ADMIN_PASSWORD`
   - `LLM_API_KEY`
   - `LLM_API_BASE`
   - `LLM_MODEL_NAME`
3. 在项目目录执行：
   ```bash
   docker compose up -d --build
   ```
4. 访问测试地址（**外网请用 8081**，见下）：
   - **推荐**：走 Nginx：`http://服务器IP:8081/`
   - `docker-compose.yml` 中 Flask 映射为 `127.0.0.1:5001:5000`，表示 **5001 仅服务器本机可访问**（公网浏览器访问 `http://服务器IP:5001/` 会失败，属预期）。本机调试可在服务器上 `curl http://127.0.0.1:5001/health`，或通过 SSH 隧道把 5001 转到本机。
5. 后台地址：`/admin`

## 推荐开放端口
- **8081**：测试阶段对外访问（经 Nginx，建议安全组只开此端口）
- **5001**：仅本机（或 SSH 隧道）访问 Flask；若确需公网直连 Flask，把 compose 中端口改为 `"5001:5000"` 并收紧安全组
- 以后切正式站时，只保留 80/443 更合适

## 常用命令
```bash
# 启动
 docker compose up -d --build

# 查看日志
 docker compose logs -f web
 docker compose logs -f nginx

# 重启
 docker compose restart

# 停止
 docker compose down
```

## 切换正式站的最稳方法
1. 先保持旧站继续跑
2. 新版在 8081（及对内的 5001）完整测试
3. 测完后再把域名或反向代理切到新版
4. 确认新版稳定后，再停旧站

## 回滚
只要旧站没删，回滚就是把访问入口重新指回旧站。
