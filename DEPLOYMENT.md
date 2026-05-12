# 部署方案

## 1. 本地开发启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问：`http://localhost:8000/docs`

## 2. Docker 单机部署

```bash
docker compose up -d --build
```

服务地址：`http://<server-ip>:8000/docs`

## 3. 生产建议（V1）

- 使用 Nginx 做反向代理并配置 HTTPS（Let's Encrypt）
- 将 `SECRET_KEY` 改为环境变量注入
- SQLite 可用于 MVP；并发上升后迁移到 PostgreSQL
- 启用日志采集（例如 Loki/ELK）
- 备份数据库与题目导入原文件

## 4. 最小可用接口

- `POST /auth/register`：注册
- `POST /auth/token`：登录获取 JWT
- `POST /questions`：创建题目（admin/researcher/teacher）
- `GET /questions`：题目列表（支持 subject/qtype 筛选）
- `POST /wrong-questions/{question_id}`：记录错题
- `GET /statistics/overview`：统计总览

## 5. 下一步扩展

- 导题任务队列（Celery/RQ）
- OCR 与 AI 标签服务
- 审核流状态机（待审核/已审核/已拒绝）
- 搜索引擎（Meilisearch/Elasticsearch）
