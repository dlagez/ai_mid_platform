"""add database table and column comments

Revision ID: d8e5f6a7b8c9
Revises: c1f0e3a7b9d2
Create Date: 2026-05-22 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "d8e5f6a7b8c9"
down_revision: Union[str, None] = "c1f0e3a7b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_COMMENTS: dict[str, str] = {
    "task_records": "后台异步任务记录表，用于记录通用任务的任务号、类型和执行状态。",
    "document_records": "通用文档文件记录表，用于记录上传到对象存储的文件基础信息。",
    "plan_document": "施工方案或模板文档表，用于记录上传文件、文件类型和解析状态。",
    "plan_section": "施工方案章节表，用于保存施工方案或模板文档解析出的章节树和正文。",
    "utility_parse_record": "工具解析记录表，用于记录 Utils/PPOCR 等工具页面的单文件解析过程和结果文件。",
    "parse_job": "文档解析任务表，用于记录 PDF/OCR 分页解析任务的文件、参数、进度和汇总质量指标。",
    "parse_page_result": "分页解析结果表，用于保存每页 OCR 的图片、原始 JSON、文本、Markdown 和质量指标。",
    "parse_result": "文档解析结果表，用于保存一次解析任务的全文 Markdown/JSON 结果和汇总指标。",
    "parse_result_section": "解析结果章节表，用于保存 parse_result 重建后的章节树、标题和正文。",
    "document_markdown_map": "全文 Markdown 页映射表，用于记录每页内容在合并 Markdown 中的字符范围。",
    "review_template": "审核模板表，用于管理从模板方案文档导入的施工方案章节框架模板。",
    "template_section_rule": "模板章节规则表，用于定义模板中必需章节、别名、必填内容点和风险等级。",
    "standard_document": "规范文档表，用于管理从规范解析结果导入的标准、规范或企业制度文件。",
    "standard_clause": "规范条文表，用于保存规范文档的条文章节、正文、强条标记和适用工程类型。",
    "review_rule_candidate": "审核规则候选表，用于保存 AI 从规范条文中抽取、待人工审核的候选规则。",
    "review_rule": "正式审核规则表，用于保存已审核发布并可被规则引擎执行的施工方案审核规则。",
    "review_task": "施工方案审核任务表，用于记录一次施工方案审核的文档、模板、状态、版本和问题统计。",
    "review_issue": "施工方案审核问题表，用于保存规则引擎发现并等待专家确认的问题。",
    "rule_execution_log": "规则执行日志表，用于记录每条模板规则或正式规则在审核任务中的执行结果。",
}


COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "task_records": {
        "id": "主键 ID。",
        "task_id": "异步任务唯一编号，通常对应 Celery/RQ 等任务 ID。",
        "task_type": "任务类型，用于区分解析、索引、审核等任务。",
        "status": "任务状态，例如 queued/running/success/failed。",
        "created_at": "记录创建时间。",
    },
    "document_records": {
        "id": "主键 ID。",
        "file_name": "原始文件名。",
        "minio_path": "文件在 MinIO 中的对象路径。",
        "uploaded_by": "上传人标识。",
        "uploaded_at": "上传时间。",
    },
    "plan_document": {
        "id": "主键 ID。",
        "file_name": "上传文件原始名称。",
        "file_path": "文件在 MinIO 中的存储路径。",
        "file_size": "文件大小，单位字节。",
        "document_type": "文档类型，template 表示模板文件，construction_plan 表示待审核施工方案。",
        "parse_status": "解析状态，例如 uploaded/parsing/parsed/failed。",
        "created_at": "记录创建时间。",
    },
    "plan_section": {
        "id": "主键 ID。",
        "document_id": "所属 plan_document.id。",
        "parent_id": "父章节 ID，空表示一级章节。",
        "level": "章节层级，1/2/3 等。",
        "title": "章节标题。",
        "section_no": "章节编号，例如 1、1.1、第一章。",
        "content": "章节正文内容。",
        "sort_no": "同一文档内的排序号。",
        "created_at": "记录创建时间。",
    },
    "utility_parse_record": {
        "id": "主键 ID。",
        "source_file_name": "原始上传文件名。",
        "source_file_path": "原始文件在 MinIO 中的路径。",
        "source_file_size": "原始文件大小，单位字节。",
        "source_content_type": "原始文件 MIME 类型。",
        "parsed_file_name": "解析后生成文件名，例如 Markdown 文件名。",
        "parsed_file_path": "解析后文件在 MinIO 中的路径。",
        "parsed_file_size": "解析后文件大小，单位字节。",
        "parser_provider": "解析方式或供应商，例如 ppocr/docling。",
        "parse_status": "解析状态，例如 uploaded/parsing/parsed/failed。",
        "parsed": "是否已完成解析。",
        "error_message": "解析失败时的错误信息。",
        "created_by": "创建人标识。",
        "created_at": "记录创建时间。",
        "completed_at": "解析完成时间。",
    },
    "parse_job": {
        "id": "主键 ID。",
        "file_id": "业务侧文件标识，用于组织 MinIO 解析结果路径。",
        "file_name": "原始文件名。",
        "file_size": "原始文件大小，单位字节。",
        "file_hash": "原始文件哈希，用于去重和追溯。",
        "page_count": "PDF 页数。",
        "source_file_path": "源文件在 MinIO 中的路径。",
        "parser_provider": "解析供应商或策略，例如 ppocr/docling。",
        "parse_mode": "解析模式，例如 page_ocr。",
        "ocr_endpoint": "调用 OCR 服务的接口路径。",
        "status": "任务状态，例如 queued/running/success/partial_success/failed。",
        "dpi": "PDF 页面渲染 DPI。",
        "batch_size": "分页提交 OCR 的批大小。",
        "page_timeout_seconds": "单页 OCR 超时时间，单位秒。",
        "min_confidence": "低质量页判断的最低置信度阈值。",
        "low_confidence_flag": "整份文档是否存在低置信度结果。",
        "total_pages": "总页数。",
        "succeeded_pages": "解析成功页数。",
        "failed_pages": "解析失败页数。",
        "low_confidence_pages": "低置信度页数。",
        "avg_confidence": "整份文档平均 OCR 置信度。",
        "block_count": "整份文档识别出的块数量。",
        "metadata": "解析参数和追溯信息 JSON，例如 dpi、parse_mode、ocr_mode。",
        "error_message": "任务失败或部分失败的错误信息。",
        "result_markdown_path": "合并全文 Markdown 在 MinIO 中的路径。",
        "result_json_path": "结构化解析 JSON 在 MinIO 中的路径。",
        "raw_result_path": "原始解析结果 JSON 在 MinIO 中的路径。",
        "created_by": "创建人标识。",
        "created_at": "记录创建时间。",
        "started_at": "任务开始时间。",
        "completed_at": "任务完成时间。",
    },
    "parse_page_result": {
        "id": "主键 ID。",
        "job_id": "所属 parse_job.id。",
        "page_no": "页码，从 1 开始。",
        "status": "页级任务状态，例如 queued/running/success/failed。",
        "image_path": "该页渲染 PNG 在 MinIO 中的路径。",
        "raw_json_path": "该页 OCR 原始 JSON 在 MinIO 中的路径。",
        "text": "该页提取出的纯文本。",
        "markdown_content": "该页生成的 Markdown 内容。",
        "rec_texts": "OCR 识别文本列表。",
        "rec_scores": "OCR 识别置信度列表。",
        "rec_polys": "OCR 文本框坐标列表。",
        "average_confidence": "该页平均 OCR 置信度。",
        "min_confidence": "该页最低 OCR 置信度。",
        "block_count": "该页识别出的块数量。",
        "low_confidence_flag": "该页是否低于质量阈值。",
        "retry_count": "该页 OCR 重试次数。",
        "error_message": "该页 OCR 失败时的错误信息。",
        "started_at": "页级任务开始时间。",
        "completed_at": "页级任务完成时间。",
    },
    "parse_result": {
        "id": "主键 ID。",
        "job_id": "所属 parse_job.id，一次解析任务对应一条汇总结果。",
        "status": "解析结果状态，例如 success/partial_success/failed。",
        "markdown_file_path": "全文 Markdown 文件在 MinIO 中的路径。",
        "json_file_path": "结构化结果 JSON 文件在 MinIO 中的路径。",
        "raw_result_file_path": "原始结果 JSON 文件在 MinIO 中的路径。",
        "markdown_file_size": "全文 Markdown 文件大小，单位字节。",
        "json_file_size": "结构化 JSON 文件大小，单位字节。",
        "page_count": "总页数。",
        "succeeded_pages": "成功页数。",
        "failed_pages": "失败页数。",
        "low_confidence_pages": "低置信度页数。",
        "avg_confidence": "平均 OCR 置信度。",
        "block_count": "全文识别块数量。",
        "metadata": "解析参数和追溯信息 JSON。",
        "created_at": "记录创建时间。",
    },
    "parse_result_section": {
        "id": "主键 ID。",
        "document_id": "所属 parse_result.id。",
        "job_id": "所属 parse_job.id。",
        "parent_id": "父章节 ID，空表示一级章节。",
        "title_level": "标题层级，1/2/3 等。",
        "title": "章节标题。",
        "section_no": "章节编号，例如 1、1.1、1.1.1。",
        "content": "章节正文原文。",
        "sort_no": "章节排序号。",
        "created_at": "记录创建时间。",
    },
    "document_markdown_map": {
        "id": "主键 ID。",
        "job_id": "所属 parse_job.id。",
        "page_result_id": "所属 parse_page_result.id。",
        "page_no": "页码，从 1 开始。",
        "markdown_start": "该页 Markdown 在全文 Markdown 中的起始字符位置。",
        "markdown_end": "该页 Markdown 在全文 Markdown 中的结束字符位置。",
        "anchor": "该页在全文 Markdown 中的锚点，例如 page-1。",
        "block_count": "该页合并进全文的块数量。",
        "created_at": "记录创建时间。",
    },
    "review_template": {
        "id": "主键 ID。",
        "name": "模板名称。",
        "code": "模板编码。",
        "work_type": "适用工程类型。",
        "source_document_id": "来源 plan_document.id。",
        "description": "模板说明。",
        "version": "模板版本。",
        "status": "模板状态，draft/active/disabled/archived。",
        "created_by": "创建人用户 ID。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "template_section_rule": {
        "id": "主键 ID。",
        "template_id": "所属 review_template.id。",
        "parent_id": "父规则 ID，表示章节规则树层级。",
        "section_code": "章节编号或编码。",
        "standard_title": "标准章节标题。",
        "level": "章节层级。",
        "order_no": "同级排序号。",
        "required": "是否必填章节。",
        "aliases": "标题别名列表，用于章节匹配。",
        "required_points": "章节必须包含的内容点列表。",
        "min_word_count": "章节最小字数或最小内容长度要求。",
        "risk_level": "规则不满足时的问题风险等级。",
        "match_strategy": "章节匹配策略。",
        "enabled": "规则是否启用。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "standard_document": {
        "id": "主键 ID。",
        "standard_code": "规范编号，例如 GB 50204-2015。",
        "standard_name": "规范名称。",
        "standard_type": "规范类型，national/industry/local/enterprise/other。",
        "version": "规范版本。",
        "effective_date": "生效日期。",
        "source_file_id": "来源文件 ID，预留用于关联文件模块。",
        "source_document_id": "来源 parse_result.id。",
        "status": "规范状态，draft/active/disabled/archived。",
        "description": "规范说明。",
        "created_by": "创建人用户 ID。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "standard_clause": {
        "id": "主键 ID。",
        "standard_id": "所属 standard_document.id。",
        "parent_id": "父条文 ID，表示条文章节树层级。",
        "chapter_no": "章节号。",
        "clause_no": "条文编号。",
        "title": "条文标题。",
        "content": "条文正文。",
        "level": "条文层级。",
        "path": "条文路径或完整章节编号路径。",
        "is_mandatory": "是否强制性条文。",
        "keywords": "条文关键词列表。",
        "applicable_work_types": "适用工程类型列表。",
        "source_section_id": "来源 parse_result_section.id。",
        "order_no": "排序号。",
        "embedding_id": "向量库或嵌入记录 ID。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "review_rule_candidate": {
        "id": "主键 ID。",
        "standard_id": "候选规则来源 standard_document.id。",
        "clause_id": "候选规则来源 standard_clause.id。",
        "rule_name": "候选规则名称。",
        "rule_type": "规则类型，例如 required_keyword/parameter_threshold。",
        "work_type": "适用工程类型。",
        "check_object": "检查对象，例如支架间距、施工顺序。",
        "operator": "参数比较符，例如 <=、>=、=。",
        "threshold_value": "参数阈值。",
        "unit": "参数单位。",
        "required_items": "必须出现的内容项列表。",
        "forbidden_items": "禁止出现的内容项列表。",
        "applicable_condition": "规则适用条件 JSON。",
        "risk_level_suggestion": "AI 建议风险等级。",
        "source_clause_text": "来源规范条文原文。",
        "ai_confidence": "AI 抽取置信度。",
        "ai_reason": "AI 抽取理由。",
        "status": "候选规则状态，pending_review/approved/rejected。",
        "reviewed_by": "审核人用户 ID。",
        "reviewed_at": "审核时间。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "review_rule": {
        "id": "主键 ID。",
        "source_candidate_id": "来源 review_rule_candidate.id。",
        "source_type": "规则来源类型，例如 standard_clause/manual。",
        "standard_id": "关联 standard_document.id。",
        "clause_id": "关联 standard_clause.id。",
        "rule_name": "正式规则名称。",
        "rule_type": "正式规则类型。",
        "work_type": "适用工程类型。",
        "check_object": "检查对象。",
        "operator": "参数比较符。",
        "threshold_value": "参数阈值。",
        "unit": "参数单位。",
        "required_items": "必须出现的内容项列表。",
        "forbidden_items": "禁止出现的内容项列表。",
        "applicable_condition": "规则适用条件 JSON。",
        "risk_level": "风险等级。",
        "status": "正式规则状态，例如 active/disabled/archived。",
        "created_by": "创建人用户 ID。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "review_task": {
        "id": "主键 ID。",
        "task_name": "审核任务名称。",
        "plan_document_id": "待审核施工方案 plan_document.id。",
        "template_id": "使用的 review_template.id。",
        "work_type": "审核工程类型，用于筛选模板和正式规则。",
        "review_mode": "审核模式，quick/standard/deep。",
        "status": "任务状态，created/running/pending_confirm/completed/failed/cancelled。",
        "version": "审核版本号，同一任务重复审核时递增。",
        "progress": "任务进度百分比。",
        "total_issue_count": "当前版本问题总数。",
        "critical_issue_count": "当前版本严重问题数量。",
        "major_issue_count": "当前版本主要问题数量。",
        "minor_issue_count": "当前版本一般问题数量。",
        "created_by": "创建人用户 ID。",
        "created_at": "记录创建时间。",
        "started_at": "任务开始时间。",
        "finished_at": "任务完成时间。",
        "error_message": "任务失败时的错误信息。",
    },
    "review_issue": {
        "id": "主键 ID。",
        "task_id": "所属 review_task.id。",
        "version": "问题所属审核版本号。",
        "issue_type": "问题类型，例如 missing_required_section/parameter_violation。",
        "risk_level": "风险等级，critical/major/minor/suggestion。",
        "issue_title": "问题标题。",
        "issue_description": "问题说明。",
        "plan_section_id": "关联 plan_section.id。",
        "plan_section_title": "命中的施工方案章节标题。",
        "plan_original_text": "问题相关的原文片段。",
        "source_type": "问题来源类型，template_rule/standard_rule/ai_risk/manual。",
        "source_rule_id": "来源正式审核规则 review_rule.id。",
        "source_template_rule_id": "来源模板章节规则 template_section_rule.id。",
        "standard_clause_id": "来源规范条文 standard_clause.id。",
        "ai_reason": "AI 判断理由，预留字段。",
        "suggestion": "整改建议。",
        "status": "问题状态，pending_confirm/accepted/ignored/modified/closed。",
        "expert_comment": "专家确认意见。",
        "confirmed_by": "确认人用户 ID。",
        "confirmed_at": "确认时间。",
        "created_at": "记录创建时间。",
        "updated_at": "记录更新时间。",
    },
    "rule_execution_log": {
        "id": "主键 ID。",
        "task_id": "所属 review_task.id。",
        "version": "日志所属审核版本号。",
        "rule_type": "执行的规则类型。",
        "rule_id": "执行的正式规则 ID。",
        "template_rule_id": "执行的模板章节规则 ID。",
        "plan_section_id": "匹配或检查的 plan_section.id。",
        "status": "执行结果，passed/failed/skipped/error。",
        "message": "执行说明或错误信息。",
        "matched_text": "命中的文本片段。",
        "expected_value": "期望值或规则要求。",
        "actual_value": "实际值或检测结果。",
        "created_at": "记录创建时间。",
    },
}


def upgrade() -> None:
    for table_name, comment in TABLE_COMMENTS.items():
        _comment_on_table(table_name, comment)
    for table_name, column_comments in COLUMN_COMMENTS.items():
        for column_name, comment in column_comments.items():
            _comment_on_column(table_name, column_name, comment)


def downgrade() -> None:
    for table_name, column_comments in COLUMN_COMMENTS.items():
        for column_name in column_comments:
            _comment_on_column(table_name, column_name, None)
    for table_name in TABLE_COMMENTS:
        _comment_on_table(table_name, None)


def _comment_on_table(table_name: str, comment: str | None) -> None:
    sql_template = "COMMENT ON TABLE %I IS NULL" if comment is None else "COMMENT ON TABLE %I IS %L"
    args = f"'{_sql_literal(table_name)}'" if comment is None else f"'{_sql_literal(table_name)}', '{_sql_literal(comment)}'"
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('{_sql_literal(table_name)}') IS NOT NULL THEN
                EXECUTE format('{sql_template}', {args});
            END IF;
        END $$;
        """
    )


def _comment_on_column(table_name: str, column_name: str, comment: str | None) -> None:
    sql_template = (
        "COMMENT ON COLUMN %I.%I IS NULL"
        if comment is None
        else "COMMENT ON COLUMN %I.%I IS %L"
    )
    args = (
        f"'{_sql_literal(table_name)}', '{_sql_literal(column_name)}'"
        if comment is None
        else f"'{_sql_literal(table_name)}', '{_sql_literal(column_name)}', '{_sql_literal(comment)}'"
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = '{_sql_literal(table_name)}'
                  AND column_name = '{_sql_literal(column_name)}'
            ) THEN
                EXECUTE format('{sql_template}', {args});
            END IF;
        END $$;
        """
    )


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")

