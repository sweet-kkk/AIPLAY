# AIPLAY 平台（MVP+）

当前仓库已实现后端 MVP+（FastAPI）：

- 认证与 RBAC：注册、登录、角色鉴权
- 题库管理：创建题目、按学科/题型/审核状态/关键词筛选
- 审核流：题目审核状态（pending/approved/rejected）
- 导题任务：导题任务创建、状态更新、列表查询
- 错题本：错题记录、标记掌握、按掌握状态筛选
- 考试模块：开始考试、提交答案、交卷、历史记录
- 统计：总题量、总用户、错题记录、待审核题量

## 快速启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问：`http://127.0.0.1:8000/docs`

## 新增接口（考试）

- `POST /exams/start`
- `POST /exams/{exam_id}/answer`
- `POST /exams/{exam_id}/complete`
- `GET /exams/history`

## 自动化测试

```bash
pytest -q
```

覆盖：健康检查、认证、题目录入/审核、考试流程主链路。
