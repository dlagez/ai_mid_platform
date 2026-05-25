import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  EyeOutlined,
  NodeIndexOutlined,
  PlayCircleOutlined,
  ProfileOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import {
  buildChapterProfiles,
  confirmReviewIssue,
  getReviewTask,
  listReviewTaskIssues,
  matchReviewCheckpoints,
  runCheckpointReview,
  startReviewTask,
  type ReviewIssue,
  type ReviewIssueConfirmRequest,
  type ReviewIssueListQuery,
  type ReviewTask,
} from "../services/reviewTaskService";

const { TextArea } = Input;

type IssueFilterValues = {
  version?: number;
  status?: string;
  risk_level?: string;
  issue_type?: string;
};

type ConfirmFormValues = Omit<ReviewIssueConfirmRequest, "action"> & {
  action: ReviewIssueConfirmRequest["action"];
};

export const ReviewTaskIssuesPage = () => {
  const { id } = useParams();
  const taskId = Number(id);
  const navigate = useNavigate();
  const [task, setTask] = useState<ReviewTask | null>(null);
  const [issues, setIssues] = useState<ReviewIssue[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<ReviewIssueListQuery>({ page: 1, page_size: 20 });
  const [selected, setSelected] = useState<ReviewIssue | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loading, setLoading] = useState({
    list: false,
    start: false,
    confirm: false,
    profiles: false,
    match: false,
    checkpointRun: false,
  });
  const [filterForm] = Form.useForm<IssueFilterValues>();
  const [confirmForm] = Form.useForm<ConfirmFormValues>();

  const load = async (nextQuery = query) => {
    if (!taskId) {
      return;
    }
    setLoading((current) => ({ ...current, list: true }));
    try {
      const [taskResult, issueResult] = await Promise.all([getReviewTask(taskId), listReviewTaskIssues(taskId, nextQuery)]);
      setTask(taskResult);
      setIssues(issueResult.items);
      setTotal(issueResult.total);
      setQuery({ ...nextQuery, page: issueResult.page, page_size: issueResult.page_size });
    } catch {
      message.error("Failed to load review task issues.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  useEffect(() => {
    void load();
  }, [taskId]);

  const startTask = async () => {
    if (!task) {
      return;
    }
    setLoading((current) => ({ ...current, start: true }));
    try {
      const result = await startReviewTask(task.id);
      message.success(`Review finished with status: ${result.status}.`);
      await load();
    } catch {
      message.error("Failed to start review task.");
    } finally {
      setLoading((current) => ({ ...current, start: false }));
    }
  };

  const buildProfiles = async () => {
    setLoading((current) => ({ ...current, profiles: true }));
    try {
      const result = await buildChapterProfiles(taskId);
      message.success(`Profiles ready: ${result.created_count} created, ${result.updated_count} updated.`);
      if (result.failed.length) {
        message.warning(`${result.failed.length} sections used rule-only profiles.`);
      }
    } catch {
      message.error("Failed to build chapter profiles.");
    } finally {
      setLoading((current) => ({ ...current, profiles: false }));
    }
  };

  const matchCheckpoints = async () => {
    setLoading((current) => ({ ...current, match: true }));
    try {
      const result = await matchReviewCheckpoints(taskId);
      message.success(`Matched checkpoints: ${result.selected_count} selected, ${result.candidate_count} candidates.`);
    } catch {
      message.error("Failed to match checkpoints.");
    } finally {
      setLoading((current) => ({ ...current, match: false }));
    }
  };

  const runCheckpointFlow = async () => {
    setLoading((current) => ({ ...current, checkpointRun: true }));
    try {
      const result = await runCheckpointReview(taskId);
      message.success(`Checkpoint review generated ${result.issue_count} issues.`);
      await load();
    } catch {
      message.error("Failed to run checkpoint review.");
    } finally {
      setLoading((current) => ({ ...current, checkpointRun: false }));
    }
  };

  const openConfirm = (issue: ReviewIssue, action: ReviewIssueConfirmRequest["action"]) => {
    setSelected(issue);
    setConfirmOpen(true);
    confirmForm.setFieldsValue({
      action,
      expert_comment: issue.expert_comment,
      issue_title: issue.issue_title,
      issue_description: issue.issue_description,
      risk_level: issue.risk_level,
      suggestion: issue.suggestion,
    });
  };

  const submitConfirm = async () => {
    if (!selected) {
      return;
    }
    const values = await confirmForm.validateFields();
    setLoading((current) => ({ ...current, confirm: true }));
    try {
      await confirmReviewIssue(selected.id, {
        ...values,
        issue_title: values.action === "modified" ? values.issue_title : undefined,
        issue_description: values.action === "modified" ? values.issue_description : undefined,
        risk_level: values.action === "modified" ? values.risk_level : undefined,
        suggestion: values.action === "modified" ? values.suggestion : undefined,
      });
      message.success("Issue updated.");
      setConfirmOpen(false);
      setSelected(null);
      await load();
    } catch {
      message.error("Failed to update issue.");
    } finally {
      setLoading((current) => ({ ...current, confirm: false }));
    }
  };

  const applyFilter = async () => {
    const values = filterForm.getFieldsValue();
    await load({ ...values, page: 1, page_size: query.page_size ?? 20 });
  };

  const handleTableChange = async (pagination: TablePaginationConfig) => {
    await load({
      ...query,
      page: pagination.current ?? 1,
      page_size: pagination.pageSize ?? 20,
    });
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{task?.task_name || `Review Task #${taskId}`}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/review-tasks")}>
            Back
          </Button>
          <Button icon={<ReloadOutlined />} loading={loading.list} onClick={() => void load()}>
            Reload
          </Button>
          {task?.status === "created" || task?.status === "failed" ? (
            <Button type="primary" icon={<PlayCircleOutlined />} loading={loading.start} onClick={() => void startTask()}>
              Start
            </Button>
          ) : task?.status !== "running" ? (
            <Button type="primary" icon={<PlayCircleOutlined />} loading={loading.start} onClick={() => void startTask()}>
              Rerun
            </Button>
          ) : null}
        </Space>
      </div>

      {task ? (
        <Card>
          <Descriptions size="small" column={4}>
            <Descriptions.Item label="Status">
              <StatusTag status={task.status} />
            </Descriptions.Item>
            <Descriptions.Item label="Current Version">v{task.version}</Descriptions.Item>
            <Descriptions.Item label="Plan Document ID">{task.plan_document_id}</Descriptions.Item>
            <Descriptions.Item label="Template ID">{task.template_id ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="Work Type">{task.work_type ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="Total Issues">{task.total_issue_count}</Descriptions.Item>
            <Descriptions.Item label="Critical">{task.critical_issue_count}</Descriptions.Item>
            <Descriptions.Item label="Major">{task.major_issue_count}</Descriptions.Item>
            <Descriptions.Item label="Minor">{task.minor_issue_count}</Descriptions.Item>
          </Descriptions>
          {task.error_message ? <Typography.Text type="danger">{task.error_message}</Typography.Text> : null}
        </Card>
      ) : null}

      <Card title="Review Methods">
        <Space wrap size={12}>
          <Button type="primary" icon={<PlayCircleOutlined />} loading={loading.start} onClick={() => void startTask()}>
            规则引擎审核
          </Button>
          <Button icon={<ProfileOutlined />} loading={loading.profiles} onClick={() => void buildProfiles()}>
            生成章节画像
          </Button>
          <Button icon={<NodeIndexOutlined />} loading={loading.match} onClick={() => void matchCheckpoints()}>
            匹配审查点
          </Button>
          <Button type="primary" icon={<PlayCircleOutlined />} loading={loading.checkpointRun} onClick={() => void runCheckpointFlow()}>
            审查点审核
          </Button>
        </Space>
      </Card>

      <Card>
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="version" label="Version">
            <Select allowClear style={{ width: 120 }} options={buildVersionOptions(task?.version ?? 1)} />
          </Form.Item>
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 170 }} options={issueStatusOptions} />
          </Form.Item>
          <Form.Item name="risk_level" label="Risk Level">
            <Select allowClear style={{ width: 150 }} options={riskLevelOptions} />
          </Form.Item>
          <Form.Item name="issue_type" label="Issue Type">
            <Input allowClear />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <Table<ReviewIssue>
          rowKey="id"
          loading={loading.list}
          dataSource={issues}
          pagination={{
            current: query.page,
            pageSize: query.page_size,
            total,
            showSizeChanger: true,
          }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            {
              title: "Risk",
              dataIndex: "risk_level",
              width: 110,
              render: (value: string | null) => <RiskTag risk={value} />,
            },
            { title: "Version", dataIndex: "version", width: 90, render: (value: number) => `v${value}` },
            { title: "Issue Type", dataIndex: "issue_type", width: 190 },
            { title: "Title", dataIndex: "issue_title", ellipsis: true },
            { title: "Plan Section", dataIndex: "plan_section_title", width: 180, ellipsis: true },
            {
              title: "Source",
              dataIndex: "source_type",
              width: 150,
              render: (value: string | null) => <SourceTag source={value} />,
            },
            {
              title: "Confidence",
              dataIndex: "confidence",
              width: 110,
              render: (value: number | null) => (value === null || value === undefined ? "-" : value.toFixed(2)),
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 140,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Actions",
              width: 300,
              render: (_, record) => (
                <Space size={6} wrap>
                  <Button size="small" icon={<EyeOutlined />} onClick={() => setSelected(record)}>
                    Detail
                  </Button>
                  {record.status === "pending_confirm" ? (
                    <>
                      <Button
                        size="small"
                        type="primary"
                        icon={<CheckCircleOutlined />}
                        onClick={() => openConfirm(record, "accepted")}
                      >
                        Accept
                      </Button>
                      <Button size="small" icon={<EditOutlined />} onClick={() => openConfirm(record, "modified")}>
                        Modify
                      </Button>
                      <Popconfirm title="Ignore this issue?" onConfirm={() => openConfirm(record, "ignored")}>
                        <Button size="small">Ignore</Button>
                      </Popconfirm>
                      <Button size="small" icon={<CloseCircleOutlined />} onClick={() => openConfirm(record, "closed")}>
                        Close
                      </Button>
                    </>
                  ) : null}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal title="Issue Detail" open={Boolean(selected) && !confirmOpen} width={860} footer={null} onCancel={() => setSelected(null)}>
        {selected ? <IssueDetail issue={selected} /> : null}
      </Modal>

      <Modal
        title="Confirm Issue"
        open={confirmOpen}
        width={720}
        confirmLoading={loading.confirm}
        onOk={() => void submitConfirm()}
        onCancel={() => setConfirmOpen(false)}
      >
        <Form form={confirmForm} layout="vertical" requiredMark={false}>
          <Form.Item name="action" label="Action" rules={[{ required: true }]}>
            <Select options={issueActionOptions} />
          </Form.Item>
          <Form.Item name="expert_comment" label="Expert Comment">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {() =>
              confirmForm.getFieldValue("action") === "modified" ? (
                <>
                  <Form.Item name="issue_title" label="Issue Title">
                    <Input />
                  </Form.Item>
                  <Form.Item name="issue_description" label="Issue Description">
                    <TextArea rows={4} />
                  </Form.Item>
                  <Form.Item name="risk_level" label="Risk Level">
                    <Select allowClear options={riskLevelOptions} />
                  </Form.Item>
                  <Form.Item name="suggestion" label="Suggestion">
                    <TextArea rows={3} />
                  </Form.Item>
                </>
              ) : null
            }
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const IssueDetail = ({ issue }: { issue: ReviewIssue }) => (
  <Space direction="vertical" size={16} style={{ width: "100%" }}>
    <Descriptions size="small" column={2}>
      <Descriptions.Item label="Risk">
        <RiskTag risk={issue.risk_level} />
      </Descriptions.Item>
      <Descriptions.Item label="Status">
        <StatusTag status={issue.status} />
      </Descriptions.Item>
      <Descriptions.Item label="Issue Type">{issue.issue_type ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Source">{issue.source_type ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Plan Section">{issue.plan_section_title ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Standard Clause ID">{issue.standard_clause_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Rule ID">{issue.source_rule_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Template Rule ID">{issue.source_template_rule_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Checkpoint ID">{issue.checkpoint_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Match Result ID">{issue.match_result_id ?? "-"}</Descriptions.Item>
      <Descriptions.Item label="Confidence">
        {issue.confidence === null || issue.confidence === undefined ? "-" : issue.confidence.toFixed(2)}
      </Descriptions.Item>
    </Descriptions>
    <TextBlock title="Issue Title" value={issue.issue_title} />
    <TextBlock title="Description" value={issue.issue_description} />
    <TextBlock title="Original Text" value={issue.plan_original_text} />
    <TextBlock title="Suggestion" value={issue.suggestion} />
    <TextBlock title="Confidence Reason" value={issue.confidence_reason} />
    <TextBlock title="AI Reason" value={issue.ai_reason} />
    <TextBlock title="Expert Comment" value={issue.expert_comment} />
  </Space>
);

const TextBlock = ({ title, value }: { title: string; value: string | null }) => (
  <div>
    <Typography.Text strong>{title}</Typography.Text>
    <Typography.Paragraph style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{value || "-"}</Typography.Paragraph>
  </div>
);

const issueStatusOptions = [
  { value: "pending_confirm", label: "pending_confirm" },
  { value: "accepted", label: "accepted" },
  { value: "ignored", label: "ignored" },
  { value: "modified", label: "modified" },
  { value: "closed", label: "closed" },
];

const issueActionOptions = [
  { value: "accepted", label: "accepted" },
  { value: "ignored", label: "ignored" },
  { value: "modified", label: "modified" },
  { value: "closed", label: "closed" },
];

const buildVersionOptions = (currentVersion: number) =>
  Array.from({ length: Math.max(currentVersion, 1) }, (_, index) => {
    const version = index + 1;
    return { value: version, label: `v${version}` };
  });

const riskLevelOptions = [
  { value: "critical", label: "critical" },
  { value: "major", label: "major" },
  { value: "minor", label: "minor" },
  { value: "suggestion", label: "suggestion" },
];

const RiskTag = ({ risk }: { risk: string | null }) => {
  const color = risk === "critical" ? "red" : risk === "major" ? "orange" : risk === "minor" ? "blue" : "default";
  return <Tag color={color}>{risk || "-"}</Tag>;
};

const SourceTag = ({ source }: { source: string | null }) => {
  const color =
    source === "checkpoint"
      ? "purple"
      : source === "standard_rule"
        ? "geekblue"
        : source === "template_rule"
          ? "cyan"
          : "default";
  return <Tag color={color}>{source || "-"}</Tag>;
};

const StatusTag = ({ status }: { status: string }) => {
  const color =
    status === "accepted" || status === "completed"
      ? "green"
      : status === "ignored" || status === "closed"
        ? "default"
        : status === "failed"
          ? "red"
          : "blue";
  return <Tag color={color}>{status}</Tag>;
};
