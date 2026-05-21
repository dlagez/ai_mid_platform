# Plan Section LLM 审核模块 - 技术方案

## 1. 背景与目标

### 1.1 业务背景

施工方案（Word 文档）的三级标题内容需要依据技术标准文档进行合规性审核。当前施工方案和技术标准都已解析并存储在数据库中，但审核工作依赖人工完成。

### 1.2 目标

- **自动化审核**：利用 LLM 自动对照技术标准审核施工方案三级标题内容
- **纯 LLM 匹配**：让大模型自主判断每个三级标题应对照哪个技术标准的哪个章节
- **结果可追溯**：保留 LLM 原始输出，支持人工复核和模型切换对比

### 1.3 不做的事情

- 不在本文档范围内：前端审核页面（后续迭代）
- 不在本文档范围内：自动修改施工方案内容（审核结果仅供参考）

## 2. 数据模型

### 2.1 `plan_review_task` — 审核任务表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger PK | 主键 |
| `plan_document_id` | Integer FK | 关联 `plan_document.id` |
| `standard_document_ids` | JSON | 技术标准文档 ID 列表 `[doc_id, ...]` |
| `status` | String(32) | `pending` / `matching` / `reviewing` / `completed` / `failed` / `cancelled` |
| `total_sections` | Integer | 三级标题总数 |
| `reviewed_count` | Integer | 已审核完成数量 |
| `error_message` | Text | 失败时的错误信息 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 最后更新时间 |

### 2.2 `plan_review_result` — 审核结果表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger PK | 主键 |
| `task_id` | Integer FK | 关联 `plan_review_task.id` |
| `plan_section_id` | Integer FK | 关联 `plan_section.id` |
| `plan_section_title` | String(512) | 冗余：三级标题名称 |
| `plan_section_content` | Text | 冗余：三级标题下的正文内容 |
| `matched_standard_section_id` | Integer | 匹配到的 `parse_result_section.id`（未匹配到则为 null） |
| `matched_standard_section_title` | String(512) | 冗余：技术标准章节标题 |
| `matched_standard_doc_id` | Integer | 冗余：来自哪个技术标准文档 |
| `matched_standard_doc_name` | String(256) | 冗余：技术标准文档名称 |
| `compliance_status` | String(32) | `compliant` / `non_compliant` / `partially_compliant` / `not_applicable` |
| `risk_level` | String(16) | `high` / `medium` / `low` / `none` |
| `llm_reasoning` | Text | LLM 的审核推理过程 |
| `suggestions` | Text | 修改建议 |
| `raw_llm_match_response` | JSON | 匹配阶段的原始 LLM 输出 |
| `raw_llm_review_response` | JSON | 审核阶段的原始 LLM 输出 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 最后更新时间 |

### 2.3 Alembic 迁移

新文件：`alembic/versions/xxxx_add_plan_review_tables.py`

## 3. 服务层设计

### 3.1 整体架构

```
backend/app/services/plan_review/
  __init__.py
  models.py                 # Pydantic 请求/响应模型
  task_service.py           # PlanReviewTaskService — 任务生命周期管理
  matcher.py                # PlanSectionMatcher — LLM 标题-章节匹配
  auditor.py                # PlanSectionAuditor — LLM 合规审核
  prompts.py                # Prompt 模板管理
```

### 3.2 PlanReviewTaskService

```python
class PlanReviewTaskService:
    """审核任务生命周期管理"""

    async def create_task(
        self,
        plan_document_id: int,
        standard_document_ids: list[int],
    ) -> PlanReviewTask:
        """创建审核任务，初始化状态为 pending"""

    async def execute_task(self, task_id: int) -> None:
        """
        执行审核任务的主流程：
        1. 将 status 置为 matching
        2. 查询所有 level=3 的 PlanSection
        3. 查询所有标准文档的 ParseResultSection
        4. 并发调用 Matcher + Auditor
        5. 更新 status 为 completed / failed
        """

    async def get_task(self, task_id: int) -> dict:
        """获取任务状态和进度"""

    async def list_tasks(self, plan_document_id: int | None = None) -> list[dict]:
        """按方案文档或全局列出任务"""
```

### 3.3 PlanSectionMatcher

```python
class PlanSectionMatcher:
    """LLM 驱动的标题-技术标准章节匹配"""

    async def match(
        self,
        plan_section: PlanSection,
        standard_sections: list[ParseResultSection],
        standard_doc_map: dict[int, str],  # doc_id -> doc_name
    ) -> MatchResult:
        """
        对单个三级标题，从技术标准所有章节中找出最相关的一个。

        流程：
        1. 构建标准章节候选列表（仅取 title + section_no，不取全文，控制 token）
        2. 组装 Prompt（见下方模板）
        3. 调用 LLM，解析 JSON 响应
        4. 返回 MatchResult(matched_section_id, confidence, reasoning)
        """
```

### 3.4 PlanSectionAuditor

```python
class PlanSectionAuditor:
    """基于匹配结果的 LLM 合规审核"""

    async def audit(
        self,
        plan_section: PlanSection,
        matched_standard: ParseResultSection | None,
        standard_doc_name: str | None,
    ) -> AuditResult:
        """
        将 plan_section 内容与匹配到的技术标准章节内容一起交给 LLM 审核。

        如果 matched_standard 为 None（没有匹配到相关标准），
        则标记为 not_applicable 并跳过审核。

        流程：
        1. 构建审核 Prompt（plan 标题 + 内容 + 标准章节标题 + 内容）
        2. 调用 LLM，解析 JSON 响应
        3. 返回 AuditResult(compliance_status, risk_level, reasoning, suggestions)
        """
```

## 4. Prompt 模板设计

### 4.1 匹配 Prompt

```
你是一个建筑工程施工方案审核专家。

当前需要对施工方案的三级标题进行审核，审核依据是相关的技术标准文档。
请根据以下施工方案的三级标题，从提供的技术标准章节列表中选择最相关的一个章节作为审核依据。

【施工方案三级标题】
标题：{title}
编号：{section_no}

【可选技术标准章节】
{standards_list}

【输出要求】
请以 JSON 格式输出，包含以下字段：
- "matched_index": 最相关章节在列表中的索引（从0开始），如无匹配则为 null
- "confidence": 匹配置信度 (0.0-1.0)
- "reasoning": 选择该章节的理由（50字以内）

只输出 JSON，不要包含其他文字。
```

### 4.2 审核 Prompt

```
你是一个建筑工程施工方案审核专家。

请根据以下技术标准的要求，审核施工方案中对应章节的内容是否合规。

【施工方案章节】
标题：{plan_title}
编号：{plan_section_no}
内容：{plan_content}

【审核依据 — 技术标准】
标准名称：{standard_doc_name}
章节：{standard_title}
内容：{standard_content}

【审核要求】
1. 判断施工方案内容是否符合技术标准的要求
2. 如果不符合，说明违反了什么要求
3. 给出具体的修改建议

【输出要求】
请以 JSON 格式输出，包含以下字段：
- "compliance_status": "compliant"（完全符合）/ "non_compliant"（不符合）/ "partially_compliant"（部分符合）/ "not_applicable"（不适用）
- "risk_level": "high"（高风险）/ "medium"（中风险）/ "low"（低风险）/ "none"（无风险）
- "reasoning": 审核推理过程，说明为什么做出此判断（200字以内）
- "suggestions": 具体的修改建议，如果不合规必须给出建议（200字以内）

只输出 JSON，不要包含其他文字。
```

### 4.3 Prompt 模板管理

使用 Python 的 `string.Template` 或 `jinja2.Template` 管理模板，存放在 `prompts.py` 中：

```python
# prompts.py
MATCH_PROMPT_TEMPLATE = """..."""   # 见 4.1
AUDIT_PROMPT_TEMPLATE = """..."""   # 见 4.2
```

后续迭代中可以迁移到数据库或配置文件管理。

## 5. API 设计

### 5.1 路由注册

```python
# backend/app/api/v1/plan_review.py
router = APIRouter(prefix="/api/v1/plan-review", tags=["plan-review"])
```

### 5.2 接口列表

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/tasks` | 创建审核任务 |
| `GET` | `/tasks` | 列出审核任务 |
| `GET` | `/tasks/{task_id}` | 获取任务详情 |
| `GET` | `/tasks/{task_id}/results` | 获取审核结果列表 |
| `GET` | `/tasks/{task_id}/results/{result_id}` | 获取单条审核结果详情 |
| `POST` | `/tasks/{task_id}/retry` | 重试失败的任务 |
| `POST` | `/tasks/{task_id}/cancel` | 取消进行中任务 |

### 5.3 请求/响应示例

**创建任务** `POST /tasks`

```json
// Request
{
  "plan_document_id": 42,
  "standard_document_ids": [101, 102]
}

// Response 201
{
  "task_id": 1,
  "plan_document_id": 42,
  "standard_document_ids": [101, 102],
  "status": "pending",
  "total_sections": 0,
  "reviewed_count": 0,
  "created_at": "2026-05-20T10:00:00"
}
```

**任务详情** `GET /tasks/{task_id}`

```json
{
  "task_id": 1,
  "plan_document_id": 42,
  "plan_document_name": "施工组织设计.docx",
  "standard_document_ids": [101, 102],
  "status": "reviewing",
  "total_sections": 56,
  "reviewed_count": 32,
  "created_at": "2026-05-20T10:00:00",
  "updated_at": "2026-05-20T10:05:30"
}
```

**审核结果** `GET /tasks/{task_id}/results/{result_id}`

```json
{
  "result_id": 15,
  "plan_section_id": 301,
  "plan_section_title": "3.2.1 钢筋绑扎工艺要求",
  "plan_section_content": "钢筋绑扎应采用...",
  "matched_standard_section_id": 2045,
  "matched_standard_section_title": "5.3 钢筋工程",
  "matched_standard_doc_name": "混凝土结构工程施工质量验收规范",
  "compliance_status": "partially_compliant",
  "risk_level": "medium",
  "llm_reasoning": "施工方案中提到了采用传统绑扎方式，但技术标准要求重要部位应采用机械绑扎...",
  "suggestions": "建议在主体结构关键部位采用机械绑扎工艺，符合GB50204的要求...",
  "created_at": "2026-05-20T10:03:15"
}
```

## 6. 并发与异步执行

### 6.1 Celery 任务

审核是长任务（每个三级标题需 2 次 LLM 调用），必须异步执行。

```python
# backend/app/workers/plan_review_tasks.py

@celery_app.task(bind=True, max_retries=2)
async def execute_review_task(self, task_id: int):
    """Celery 异步任务：执行一个审核任务"""
    service = PlanReviewTaskService()
    await service.execute_task(task_id)
```

### 6.2 LLM 调用并发控制

在 `execute_task` 内部，对三级标题的审核使用 `asyncio.Semaphore` 控制并发：

```python
# 控制同时进行的 LLM 调用数量，避免限流
semaphore = asyncio.Semaphore(5)

async def process_section(section):
    async with semaphore:
        # match + audit
        ...

await asyncio.gather(*[process_section(s) for s in level3_sections])
```

### 6.3 执行流程时序

```
用户 POST /tasks
    │
    ▼
API 创建 task 记录 (status=pending)
    │
    ▼
触发 Celery execute_review_task.delay(task_id)
    │
    ▼
Celery Worker 执行:
    ├── status = "matching"
    ├── 查询 level=3 PlanSections
    ├── 查询 ParseResultSections (standard_document_ids)
    ├── 并发处理每个 section:
    │   ├── Matcher: LLM 匹配 → matched_standard
    │   └── Auditor: LLM 审核 → result
    │       └── 写入 plan_review_result
    ├── reviewed_count += N
    ├── status = "completed" (或 "failed")
    └── 任务结束
```

## 7. 错误处理

| 场景 | 处理方式 |
|---|---|
| LLM 匹配返回无效 JSON | 重试 1 次，仍失败则标记该条结果为 `not_applicable` |
| LLM 审核返回无效 JSON | 重试 1 次，仍失败则记录 `raw_response`，状态置 `failed` |
| LLM 调用超时/限流 | Celery 自动重试（max_retries=2），指数退避 |
| 标准文档无内容 | 任务整体标记为 `failed`，`error_message` 说明原因 |
| 标准文档章节太多 | 在 Prompt 中提示 LLM 分批处理（如果候选 > 50 条，拆分为多个 Prompt） |

## 8. 文件清单

### 新增文件

| 文件 | 说明 |
|---|---|
| `backend/app/db/models.py` (修改) | 新增 `PlanReviewTask`、`PlanReviewResult` 模型 |
| `backend/app/services/plan_review/__init__.py` | 包初始化 |
| `backend/app/services/plan_review/models.py` | Pydantic 请求/响应模型 |
| `backend/app/services/plan_review/task_service.py` | 任务生命周期管理 |
| `backend/app/services/plan_review/matcher.py` | LLM 标题-章节匹配 |
| `backend/app/services/plan_review/auditor.py` | LLM 合规审核 |
| `backend/app/services/plan_review/prompts.py` | Prompt 模板 |
| `backend/app/api/v1/plan_review.py` | API 路由 |
| `backend/app/workers/plan_review_tasks.py` | Celery 异步任务 |
| `alembic/versions/xxxx_add_plan_review_tables.py` | 数据库迁移 |
| `frontend/src/services/planReviewService.ts` | 前端 API 客户端 |
| `frontend/src/types/planReview.ts` | 前端 TypeScript 类型 |

### 修改文件

| 文件 | 说明 |
|---|---|
| `backend/app/db/models.py` | 新增两个模型类 |
| `backend/app/api/v1/__init__.py` | 注册新路由 |

## 9. 实施步骤

1. **数据模型 + 迁移** — 定义 `PlanReviewTask`、`PlanReviewResult`，生成 alembic 迁移
2. **Prompt 模板** — 在 `prompts.py` 中定义匹配和审核的 Prompt 模板
3. **Matcher 服务** — 实现 `PlanSectionMatcher`，支持从标准章节列表匹配到最相关章节
4. **Auditor 服务** — 实现 `PlanSectionAuditor`，基于匹配结果做合规审核
5. **Task Service** — 实现 `PlanReviewTaskService`，编排 Matcher + Auditor，处理并发和进度
6. **Celery 任务** — 在 `workers/plan_review_tasks.py` 中定义异步任务
7. **API 路由** — 实现 `/plan-review/tasks` 系列接口
8. **前端 API 客户端** — 在 `planReviewService.ts` 中封装 API 调用
