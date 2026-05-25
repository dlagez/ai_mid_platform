import { useEffect, useState } from "react";
import { useGetIdentity } from "@refinedev/core";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  createReviewCheckpoint,
  deleteReviewCheckpoint,
  listCheckpointGenerationJobs,
  listReviewCheckpoints,
  updateReviewCheckpoint,
  type CheckpointGenerationJob,
  type ReviewCheckpoint,
  type ReviewCheckpointPayload,
  type ReviewCheckpointQuery,
} from "../services/reviewCheckpointService";

const { TextArea } = Input;

type CheckpointFilterValues = {
  status?: string;
  checkpoint_type?: string;
  domain?: string;
  work_type?: string;
  keyword?: string;
};

type CheckpointFormValues = Omit<ReviewCheckpointPayload, "parameters" | "applicable_condition"> & {
  parameters?: string;
  applicable_condition?: string;
};

export const ReviewCheckpointsPage = () => {
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState<ReviewCheckpoint[]>([]);
  const [recentJobs, setRecentJobs] = useState<CheckpointGenerationJob[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<ReviewCheckpointQuery>({ page: 1, page_size: 20 });
  const [editing, setEditing] = useState<ReviewCheckpoint | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [loading, setLoading] = useState({ list: false, save: false, create: false, delete: false, jobs: false });
  const [filterForm] = Form.useForm<CheckpointFilterValues>();
  const [editForm] = Form.useForm<CheckpointFormValues>();
  const [createForm] = Form.useForm<CheckpointFormValues>();

  const load = async (nextQuery = query) => {
    setLoading((current) => ({ ...current, list: true }));
    try {
      const result = await listReviewCheckpoints(nextQuery);
      setItems(result.items);
      setTotal(result.total);
      setQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
    } catch {
      message.error("Failed to load review checkpoints.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  const loadRecentJobs = async () => {
    setLoading((current) => ({ ...current, jobs: true }));
    try {
      const result = await listCheckpointGenerationJobs({ page: 1, page_size: 3 });
      setRecentJobs(result.items);
    } catch {
      message.error("Failed to load checkpoint generation progress.");
    } finally {
      setLoading((current) => ({ ...current, jobs: false }));
    }
  };

  useEffect(() => {
    void load();
    void loadRecentJobs();
  }, []);

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

  const openEdit = (checkpoint: ReviewCheckpoint) => {
    setEditing(checkpoint);
    editForm.setFieldsValue(toFormValues(checkpoint));
  };

  const openCreate = () => {
    createForm.resetFields();
    createForm.setFieldsValue({
      checkpoint_type: "required_content",
      risk_level: "major",
      status: "active",
      priority: 0,
      is_mandatory: false,
      parameters: "{}",
      applicable_condition: "{}",
    });
    setCreateOpen(true);
  };

  const saveEdit = async () => {
    if (!editing || !isAdmin) {
      return;
    }
    const values = await editForm.validateFields();
    const payload = normalizePayload(values);
    if (!payload) {
      message.error("JSON fields must be valid.");
      return;
    }
    setLoading((current) => ({ ...current, save: true }));
    try {
      const result = await updateReviewCheckpoint(editing.id, payload);
      setEditing(result);
      message.success("Checkpoint saved.");
      await load();
    } catch {
      message.error("Failed to save checkpoint.");
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  const create = async () => {
    if (!isAdmin) {
      return;
    }
    const values = await createForm.validateFields();
    const payload = normalizePayload(values);
    if (!payload?.checkpoint_name || !payload.checkpoint_type) {
      message.error("Checkpoint name and type are required.");
      return;
    }
    setLoading((current) => ({ ...current, create: true }));
    try {
      await createReviewCheckpoint(payload);
      message.success("Checkpoint created.");
      setCreateOpen(false);
      await load();
    } catch {
      message.error("Failed to create checkpoint.");
    } finally {
      setLoading((current) => ({ ...current, create: false }));
    }
  };

  const archive = async (checkpoint: ReviewCheckpoint) => {
    setLoading((current) => ({ ...current, delete: true }));
    try {
      await deleteReviewCheckpoint(checkpoint.id);
      message.success("Checkpoint archived.");
      await load();
    } catch {
      message.error("Failed to archive checkpoint.");
    } finally {
      setLoading((current) => ({ ...current, delete: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Review Checkpoints</h1>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            loading={loading.list || loading.jobs}
            onClick={() => {
              void load();
              void loadRecentJobs();
            }}
          >
            Refresh
          </Button>
          {isAdmin ? (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              New Checkpoint
            </Button>
          ) : null}
        </Space>
      </div>

      <Card title="Generation Progress" loading={loading.jobs}>
        {recentJobs.length ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            {recentJobs.map((job) => (
              <div key={job.id}>
                <Space wrap>
                  <Typography.Text strong>Job #{job.id}</Typography.Text>
                  <GenerationStatusTag status={job.status} />
                  <Typography.Text type="secondary">
                    Clauses {job.processed_clauses}/{job.total_clauses}, created {job.created_count}, failed{" "}
                    {job.failed_count}, skipped {job.skipped_count}
                  </Typography.Text>
                </Space>
                <Progress
                  percent={progressPercent(job)}
                  size="small"
                  status={job.status === "failed" ? "exception" : job.status === "running" ? "active" : "normal"}
                />
              </div>
            ))}
          </Space>
        ) : (
          <Typography.Text type="secondary">No checkpoint generation jobs yet.</Typography.Text>
        )}
      </Card>

      <Card>
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 150 }} options={checkpointStatusOptions} />
          </Form.Item>
          <Form.Item name="checkpoint_type" label="Type">
            <Select allowClear style={{ width: 210 }} options={checkpointTypeOptions} />
          </Form.Item>
          <Form.Item name="domain" label="Domain">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="work_type" label="Work Type">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="keyword" label="Keyword">
            <Input allowClear />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <Table<ReviewCheckpoint>
          rowKey="id"
          loading={loading.list}
          dataSource={items}
          pagination={{
            current: query.page,
            pageSize: query.page_size,
            total,
            showSizeChanger: true,
          }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            { title: "Code", dataIndex: "checkpoint_code", width: 140, ellipsis: true },
            { title: "Checkpoint", dataIndex: "checkpoint_name", ellipsis: true },
            { title: "Type", dataIndex: "checkpoint_type", width: 190 },
            { title: "Domain", dataIndex: "domain", width: 130 },
            { title: "Work Type", dataIndex: "work_type", width: 130 },
            { title: "Clause", dataIndex: "clause_no", width: 120 },
            {
              title: "Targets",
              dataIndex: "target_objects",
              width: 220,
              render: (values: string[]) => <TagList values={values} />,
            },
            {
              title: "Risk",
              dataIndex: "risk_level",
              width: 100,
              render: (value: string) => <RiskTag risk={value} />,
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 120,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Actions",
              width: 160,
              render: (_, record) => (
                <Space size={6} wrap>
                  <Button size="small" icon={isAdmin ? <EditOutlined /> : <EyeOutlined />} onClick={() => openEdit(record)}>
                    {isAdmin ? "Edit" : "Detail"}
                  </Button>
                  {isAdmin ? (
                    <Popconfirm
                      title="Archive this checkpoint?"
                      okText="Archive"
                      okButtonProps={{ danger: true }}
                      onConfirm={() => void archive(record)}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} loading={loading.delete}>
                        Archive
                      </Button>
                    </Popconfirm>
                  ) : null}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Review Checkpoint"
        open={Boolean(editing)}
        width={920}
        footer={
          editing ? (
            <Space>
              <Button onClick={() => setEditing(null)}>Close</Button>
              {isAdmin ? (
                <Button type="primary" icon={<SaveOutlined />} loading={loading.save} onClick={() => void saveEdit()}>
                  Save
                </Button>
              ) : null}
            </Space>
          ) : null
        }
        onCancel={() => setEditing(null)}
      >
        <CheckpointForm form={editForm} disabled={!isAdmin} />
      </Modal>

      <Modal
        title="New Review Checkpoint"
        open={createOpen}
        width={920}
        confirmLoading={loading.create}
        onOk={() => void create()}
        onCancel={() => setCreateOpen(false)}
      >
        <CheckpointForm form={createForm} disabled={!isAdmin} />
      </Modal>
    </div>
  );
};

const CheckpointForm = ({
  form,
  disabled,
}: {
  form: ReturnType<typeof Form.useForm<CheckpointFormValues>>[0];
  disabled: boolean;
}) => (
  <Form form={form} layout="vertical" disabled={disabled} requiredMark={false}>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="checkpoint_code" label="Code" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="checkpoint_type" label="Type" style={{ flex: 1 }} rules={[{ required: true }]}>
        <Select options={checkpointTypeOptions} />
      </Form.Item>
      <Form.Item name="status" label="Status" style={{ width: 150 }}>
        <Select options={checkpointStatusOptions} />
      </Form.Item>
    </Space>
    <Form.Item name="checkpoint_name" label="Checkpoint Name" rules={[{ required: true }]}>
      <Input />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="domain" label="Domain" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="subdomain" label="Subdomain" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="work_type" label="Work Type" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
    </Space>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="standard_id" label="Standard ID" style={{ width: 140 }}>
        <InputNumber min={1} style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item name="clause_id" label="Clause ID" style={{ width: 140 }}>
        <InputNumber min={1} style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item name="clause_no" label="Clause No" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
    </Space>
    <Form.Item name="clause_text" label="Clause Text">
      <TextArea rows={4} />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="chapter_types" label="Chapter Types" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} options={chapterTypeOptions} />
      </Form.Item>
      <Form.Item name="target_objects" label="Target Objects" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
      <Form.Item name="target_parameters" label="Target Parameters" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
    </Space>
    <Form.Item name="keywords" label="Keywords">
      <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
    </Form.Item>
    <Form.Item name="check_goal" label="Check Goal">
      <TextArea rows={3} />
    </Form.Item>
    <Form.Item name="check_method" label="Check Method">
      <Input />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="expected_items" label="Expected Items" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
      <Form.Item name="forbidden_items" label="Forbidden Items" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
    </Space>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="risk_level" label="Risk Level" style={{ width: 150 }}>
        <Select options={riskLevelOptions} />
      </Form.Item>
      <Form.Item name="priority" label="Priority" style={{ width: 140 }}>
        <InputNumber style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item name="is_mandatory" label="Mandatory" valuePropName="checked" style={{ width: 130 }}>
        <Switch />
      </Form.Item>
    </Space>
    <Form.Item name="parameters" label="Parameters JSON">
      <TextArea rows={4} />
    </Form.Item>
    <Form.Item name="applicable_condition" label="Applicable Condition JSON">
      <TextArea rows={4} />
    </Form.Item>
  </Form>
);

const checkpointTypeOptions = [
  { value: "required_content", label: "required_content" },
  { value: "parameter_threshold", label: "parameter_threshold" },
  { value: "forbidden_content", label: "forbidden_content" },
  { value: "procedure_required", label: "procedure_required" },
  { value: "semantic_check", label: "semantic_check" },
  { value: "cross_section_consistency", label: "cross_section_consistency" },
];

const checkpointStatusOptions = [
  { value: "draft", label: "draft" },
  { value: "active", label: "active" },
  { value: "disabled", label: "disabled" },
  { value: "archived", label: "archived" },
];

const chapterTypeOptions = [
  { value: "project_overview", label: "project_overview" },
  { value: "basis", label: "basis" },
  { value: "construction_deployment", label: "construction_deployment" },
  { value: "construction_plan", label: "construction_plan" },
  { value: "construction_technology", label: "construction_technology" },
  { value: "quality_control", label: "quality_control" },
  { value: "safety_control", label: "safety_control" },
  { value: "emergency", label: "emergency" },
  { value: "calculation", label: "calculation" },
];

const riskLevelOptions = [
  { value: "critical", label: "critical" },
  { value: "major", label: "major" },
  { value: "minor", label: "minor" },
  { value: "suggestion", label: "suggestion" },
];

const TagList = ({ values }: { values?: string[] }) => (
  <Space size={4} wrap>
    {(values || []).slice(0, 4).map((value) => (
      <Tag key={value}>{value}</Tag>
    ))}
    {(values || []).length > 4 ? <Typography.Text type="secondary">+{(values || []).length - 4}</Typography.Text> : null}
  </Space>
);

const RiskTag = ({ risk }: { risk: string }) => {
  const color = risk === "critical" ? "red" : risk === "major" ? "orange" : risk === "minor" ? "blue" : "default";
  return <Tag color={color}>{risk || "-"}</Tag>;
};

const StatusTag = ({ status }: { status: string }) => {
  const color = status === "active" ? "green" : status === "disabled" ? "red" : status === "archived" ? "default" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const GenerationStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success"
      ? "green"
      : status === "partial_success"
        ? "gold"
        : status === "failed"
          ? "red"
          : status === "running"
            ? "blue"
            : "default";
  return <Tag color={color}>{status}</Tag>;
};

const progressPercent = (job: CheckpointGenerationJob) => {
  if (!job.total_clauses) {
    return 0;
  }
  return Math.round((job.processed_clauses / job.total_clauses) * 100);
};

const toFormValues = (checkpoint: ReviewCheckpoint): CheckpointFormValues => ({
  ...checkpoint,
  parameters: JSON.stringify(checkpoint.parameters ?? {}, null, 2),
  applicable_condition: JSON.stringify(checkpoint.applicable_condition ?? {}, null, 2),
});

const normalizePayload = (values: CheckpointFormValues): ReviewCheckpointPayload | null => {
  try {
    return {
      ...values,
      parameters: values.parameters ? JSON.parse(values.parameters) : {},
      applicable_condition: values.applicable_condition ? JSON.parse(values.applicable_condition) : {},
    };
  } catch {
    return null;
  }
};
