import { useEffect, useMemo, useState } from "react";
import { Button, Card, Form, Input, InputNumber, Select, Space, Table, Tag, Typography, message } from "antd";
import type { TablePaginationConfig } from "antd";
import { BranchesOutlined, EyeOutlined, ReloadOutlined, RobotOutlined, SearchOutlined } from "@ant-design/icons";
import { listDocuments, type DocumentRecord } from "../services/documentService";
import { listStandards, type StandardDocument } from "../services/standardService";
import {
  createTocMatchJob,
  getTocMatchJob,
  listTocMatchJobs,
  type TocMatchItem,
  type TocMatchJob,
  type TocMatchJobQuery,
} from "../services/tocMatchingService";

type RunFormValues = {
  plan_document_id: number;
  standard_id: number;
  model?: string;
};

type FilterValues = {
  plan_document_id?: number;
  standard_id?: number;
  status?: string;
};

export const TocMatchingPage = () => {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [standards, setStandards] = useState<StandardDocument[]>([]);
  const [jobs, setJobs] = useState<TocMatchJob[]>([]);
  const [items, setItems] = useState<TocMatchItem[]>([]);
  const [selectedJob, setSelectedJob] = useState<TocMatchJob | null>(null);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<TocMatchJobQuery>({ page: 1, page_size: 10 });
  const [loading, setLoading] = useState({ options: false, jobs: false, run: false, detail: false });
  const [runForm] = Form.useForm<RunFormValues>();
  const [filterForm] = Form.useForm<FilterValues>();

  const documentOptions = useMemo(
    () =>
      documents.map((document) => ({
        value: document.id,
        label: `${document.id} - ${document.file_name} (${document.parse_status})`,
      })),
    [documents],
  );

  const standardOptions = useMemo(
    () =>
      standards.map((standard) => ({
        value: standard.id,
        label: `${standard.id} - ${standard.standard_name}${standard.standard_code ? ` / ${standard.standard_code}` : ""}`,
      })),
    [standards],
  );

  const loadOptions = async () => {
    setLoading((current) => ({ ...current, options: true }));
    try {
      const [documentResult, standardResult] = await Promise.all([
        listDocuments({ document_type: "construction_plan" }),
        listStandards(),
      ]);
      setDocuments(documentResult);
      setStandards(standardResult.items);
    } catch {
      message.error("Failed to load documents or standards.");
    } finally {
      setLoading((current) => ({ ...current, options: false }));
    }
  };

  const loadJobs = async (nextQuery = query, selectFirst = false) => {
    setLoading((current) => ({ ...current, jobs: true }));
    try {
      const result = await listTocMatchJobs(nextQuery);
      setJobs(result.items);
      setTotal(result.total);
      setQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
      if (selectFirst && result.items[0]) {
        await loadDetail(result.items[0].id);
      } else if (!result.items.some((job) => job.id === selectedJob?.id)) {
        setSelectedJob(null);
        setItems([]);
      }
    } catch {
      message.error("Failed to load TOC match jobs.");
    } finally {
      setLoading((current) => ({ ...current, jobs: false }));
    }
  };

  const loadDetail = async (jobId: number) => {
    setLoading((current) => ({ ...current, detail: true }));
    try {
      const detail = await getTocMatchJob(jobId);
      setSelectedJob(detail.job);
      setItems(detail.items);
    } catch {
      message.error("Failed to load match result.");
    } finally {
      setLoading((current) => ({ ...current, detail: false }));
    }
  };

  useEffect(() => {
    void loadOptions();
    void loadJobs(undefined, true);
  }, []);

  const runMatch = async () => {
    const values = await runForm.validateFields();
    setLoading((current) => ({ ...current, run: true }));
    try {
      const detail = await createTocMatchJob({
        plan_document_id: values.plan_document_id,
        standard_id: values.standard_id,
        model: values.model || null,
      });
      message.success(`TOC match job #${detail.job.id} completed.`);
      setSelectedJob(detail.job);
      setItems(detail.items);
      await loadJobs({ ...query, page: 1 });
    } catch {
      message.error("Failed to run TOC matching.");
    } finally {
      setLoading((current) => ({ ...current, run: false }));
    }
  };

  const applyFilter = async () => {
    const values = filterForm.getFieldsValue();
    await loadJobs({ ...values, page: 1, page_size: query.page_size ?? 10 }, true);
  };

  const handleTableChange = async (pagination: TablePaginationConfig) => {
    await loadJobs({
      ...query,
      page: pagination.current ?? 1,
      page_size: pagination.pageSize ?? 10,
    });
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Table of Contents Matching and Review</h1>
        <Button icon={<ReloadOutlined />} loading={loading.jobs || loading.options} onClick={() => void loadJobs()}>
          Refresh
        </Button>
      </div>

      <Card>
        <Form form={runForm} layout="inline" className="table-filter-form" requiredMark={false}>
          <Form.Item name="plan_document_id" label="Construction Plan" rules={[{ required: true }]}>
            <Select showSearch loading={loading.options} optionFilterProp="label" style={{ width: 300 }} options={documentOptions} />
          </Form.Item>
          <Form.Item name="standard_id" label="Standard" rules={[{ required: true }]}>
            <Select showSearch loading={loading.options} optionFilterProp="label" style={{ width: 320 }} options={standardOptions} />
          </Form.Item>
          <Form.Item name="model" label="Model">
            <Input placeholder="default" style={{ width: 170 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<RobotOutlined />} loading={loading.run} onClick={() => void runMatch()}>
              Run Matching
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card>
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="plan_document_id" label="Plan ID">
            <InputNumber min={1} style={{ width: 130 }} />
          </Form.Item>
          <Form.Item name="standard_id" label="Standard ID">
            <InputNumber min={1} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 140 }} options={statusOptions} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <Table<TocMatchJob>
          rowKey="id"
          loading={loading.jobs}
          dataSource={jobs}
          pagination={{ current: query.page, pageSize: query.page_size, total, showSizeChanger: true }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            { title: "Job ID", dataIndex: "id", width: 90 },
            { title: "Plan ID", dataIndex: "plan_document_id", width: 100 },
            { title: "Standard ID", dataIndex: "standard_id", width: 120 },
            { title: "Status", dataIndex: "status", width: 120, render: (value: string) => <StatusTag status={value} /> },
            { title: "Matches", dataIndex: "match_count", width: 100 },
            { title: "Reviewed", dataIndex: "reviewed_count", width: 110 },
            {
              title: "Issues",
              dataIndex: "issue_count",
              width: 100,
              render: (value: number) => <Tag color={value > 0 ? "red" : "green"}>{value ?? 0}</Tag>,
            },
            { title: "Model", dataIndex: "model", width: 150, render: (value: string | null) => value || "default" },
            { title: "Error", dataIndex: "error_message", ellipsis: true, render: (value: string | null) => value || "-" },
            { title: "Created At", dataIndex: "created_at", width: 180, render: formatDateTime },
            {
              title: "Actions",
              width: 100,
              render: (_, record) => (
                <Button size="small" icon={<EyeOutlined />} onClick={() => void loadDetail(record.id)}>
                  View
                </Button>
              ),
            },
          ]}
        />
      </Card>

      <Card
        title={
          <Space>
            <BranchesOutlined />
            <span>Matching Result</span>
            {selectedJob ? <Tag>Job #{selectedJob.id}</Tag> : null}
          </Space>
        }
      >
        <Table<TocMatchItem>
          rowKey="id"
          loading={loading.detail}
          dataSource={items}
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: selectedJob ? "No matches." : "Select a match job." }}
          expandable={{
            expandedRowRender: (record) => <IssueList record={record} />,
            rowExpandable: (record) => Boolean(record.review_error || record.review_issues.length),
          }}
          columns={[
            {
              title: "Standard Chapter",
              dataIndex: "standard_title",
              width: 320,
              render: (_, record) => (
                <Typography.Text>
                  {formatNode(record.standard_section_no, record.standard_title)}
                  {record.standard_path ? <Typography.Text type="secondary"> / {record.standard_path}</Typography.Text> : null}
                </Typography.Text>
              ),
            },
            {
              title: "Plan Chapter",
              dataIndex: "plan_title",
              width: 320,
              render: (_, record) => (
                <Typography.Text>
                  {formatNode(record.plan_section_no, record.plan_title)}
                  {record.plan_path ? <Typography.Text type="secondary"> / {record.plan_path}</Typography.Text> : null}
                </Typography.Text>
              ),
            },
            { title: "Type", dataIndex: "match_type", width: 150 },
            {
              title: "Confidence",
              dataIndex: "confidence",
              width: 120,
              render: (value: number | null) => (value == null ? "-" : `${Math.round(value * 100)}%`),
            },
            {
              title: "Review",
              dataIndex: "review_status",
              width: 130,
              render: (value: string, record) => (
                <Space size={4}>
                  <StatusTag status={value} />
                  <Tag color={record.review_issues.length > 0 ? "red" : "green"}>{record.review_issues.length}</Tag>
                </Space>
              ),
            },
            { title: "Reason", dataIndex: "reason", ellipsis: true },
          ]}
        />
      </Card>
    </div>
  );
};

const statusOptions = [
  { value: "running", label: "running" },
  { value: "success", label: "success" },
  { value: "failed", label: "failed" },
];

const StatusTag = ({ status }: { status: string }) => {
  const color = status === "success" ? "green" : status === "failed" ? "red" : "processing";
  return <Tag color={color}>{status}</Tag>;
};

const formatDateTime = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const formatNode = (no: string | null, title: string | null) => [no, title].filter(Boolean).join(" ") || "-";

const IssueList = ({ record }: { record: TocMatchItem }) => {
  if (record.review_error) {
    return <Typography.Text type="danger">{record.review_error}</Typography.Text>;
  }
  if (!record.review_issues.length) {
    return <Typography.Text type="secondary">No issues found.</Typography.Text>;
  }
  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {record.review_issues.map((issue, index) => (
        <div className="toc-review-issue" key={`${record.id}-${index}`}>
          <Typography.Text strong>Issue {index + 1}</Typography.Text>
          <div>
            <Typography.Text type="secondary">Standard Basis: </Typography.Text>
            <Typography.Text>{issue.standard_basis || "-"}</Typography.Text>
          </div>
          <div>
            <Typography.Text type="secondary">Plan Evidence: </Typography.Text>
            <Typography.Text>{issue.plan_evidence || "-"}</Typography.Text>
          </div>
          <div>
            <Typography.Text type="secondary">Problem: </Typography.Text>
            <Typography.Text>{issue.problem_description || "-"}</Typography.Text>
          </div>
          <div>
            <Typography.Text type="secondary">Suggestion: </Typography.Text>
            <Typography.Text>{issue.rectification_suggestion || "-"}</Typography.Text>
          </div>
        </div>
      ))}
    </Space>
  );
};
