import { useEffect, useMemo, useState } from "react";
import { useGetIdentity } from "@refinedev/core";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tree,
  Typography,
  message,
} from "antd";
import type { DataNode } from "antd/es/tree";
import {
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  createReviewCheckpoint,
  deleteReviewCheckpoint,
  getReviewCheckpointTree,
  listCheckpointGenerationJobs,
  updateReviewCheckpoint,
  type CheckpointGenerationJob,
  type ReviewCheckpoint,
  type ReviewCheckpointPayload,
  type ReviewCheckpointQuery,
  type ReviewCheckpointTreeResult,
} from "../services/reviewCheckpointService";
import { listStandards, type StandardClause, type StandardDocument } from "../services/standardService";

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
  const [standards, setStandards] = useState<StandardDocument[]>([]);
  const [recentJobs, setRecentJobs] = useState<CheckpointGenerationJob[]>([]);
  const [selectedStandardId, setSelectedStandardId] = useState<number | null>(null);
  const [checkpointTree, setCheckpointTree] = useState<ReviewCheckpointTreeResult | null>(null);
  const [selectedClauseId, setSelectedClauseId] = useState<number | null>(null);
  const [query, setQuery] = useState<ReviewCheckpointQuery>({});
  const [editing, setEditing] = useState<ReviewCheckpoint | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<number | null>(null);
  const [loading, setLoading] = useState({ standards: false, tree: false, save: false, create: false, delete: false, jobs: false });
  const [filterForm] = Form.useForm<CheckpointFilterValues>();
  const [editForm] = Form.useForm<CheckpointFormValues>();
  const [createForm] = Form.useForm<CheckpointFormValues>();

  const loadStandards = async () => {
    setLoading((current) => ({ ...current, standards: true }));
    try {
      const result = await listStandards();
      setStandards(result.items);
      const nextStandardId = selectedStandardId && result.items.some((standard) => standard.id === selectedStandardId)
        ? selectedStandardId
        : result.items[0]?.id ?? null;
      setSelectedStandardId(nextStandardId);
      if (nextStandardId) {
        await loadCheckpointTree(nextStandardId, query);
      }
    } catch {
      message.error("Failed to load standards.");
    } finally {
      setLoading((current) => ({ ...current, standards: false }));
    }
  };

  const loadCheckpointTree = async (standardId = selectedStandardId, nextQuery = query, preserveSelection = true) => {
    if (!standardId) {
      setCheckpointTree(null);
      setSelectedClauseId(null);
      return;
    }
    setLoading((current) => ({ ...current, tree: true }));
    try {
      const result = await getReviewCheckpointTree({ ...nextQuery, standard_id: standardId });
      setCheckpointTree(result);
      setQuery(nextQuery);
      setSelectedClauseId((current) =>
        preserveSelection && current && result.clauses.some((clause) => clause.id === current)
          ? current
          : findFirstCheckpointClauseId(result.checkpoints) ?? result.clauses[0]?.id ?? null,
      );
    } catch {
      message.error("Failed to load review checkpoint tree.");
    } finally {
      setLoading((current) => ({ ...current, tree: false }));
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
    void loadStandards();
    void loadRecentJobs();
  }, []);

  const applyFilter = async () => {
    const values = filterForm.getFieldsValue();
    setSelectedClauseId(null);
    await loadCheckpointTree(selectedStandardId, values, false);
  };

  const selectStandard = async (standardId: number) => {
    setSelectedStandardId(standardId);
    setSelectedClauseId(null);
    await loadCheckpointTree(standardId, query, false);
  };

  const openEdit = (checkpoint: ReviewCheckpoint) => {
    setEditing(checkpoint);
    editForm.setFieldsValue(toFormValues(checkpoint));
  };

  const openCreate = () => {
    createForm.resetFields();
    createForm.setFieldsValue({
      standard_id: selectedStandardId ?? undefined,
      clause_id: selectedClause?.id,
      clause_no: selectedClause?.clause_no,
      clause_text: selectedClause?.content,
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
      await loadCheckpointTree();
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
      await loadCheckpointTree();
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
      await loadCheckpointTree();
    } catch {
      message.error("Failed to archive checkpoint.");
    } finally {
      setLoading((current) => ({ ...current, delete: false }));
    }
  };

  const checkpointsByClauseId = useMemo(() => groupCheckpointsByClauseId(checkpointTree?.checkpoints ?? []), [checkpointTree]);
  const selectedClause = useMemo(
    () => (checkpointTree && selectedClauseId ? checkpointTree.clauses.find((clause) => clause.id === selectedClauseId) ?? null : null),
    [checkpointTree, selectedClauseId],
  );
  const selectedCheckpoints = selectedClause ? checkpointsByClauseId.get(selectedClause.id) ?? [] : [];

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Review Checkpoints</h1>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            loading={loading.standards || loading.tree || loading.jobs}
            onClick={() => {
              void loadStandards();
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
          <Form.Item label="Standard">
            <Select
              showSearch
              style={{ width: 320 }}
              loading={loading.standards}
              value={selectedStandardId}
              optionFilterProp="label"
              options={standards.map((standard) => ({
                value: standard.id,
                label: standard.standard_code
                  ? `${standard.standard_code} ${standard.standard_name}`
                  : standard.standard_name,
              }))}
              onChange={(value) => void selectStandard(value)}
            />
          </Form.Item>
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
      </Card>

      <Card
        title={
          checkpointTree?.standard
            ? `Review Checkpoint Tree - ${checkpointTree.standard.standard_name}`
            : "Review Checkpoint Tree"
        }
        loading={loading.tree}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={9}>
            <div className="plan-section-tree review-checkpoint-tree">
              {checkpointTree?.clauses.length ? (
                <Tree
                  blockNode
                  defaultExpandAll
                  selectedKeys={selectedClauseId ? [String(selectedClauseId)] : []}
                  treeData={toClauseTreeData(checkpointTree.clauses, checkpointsByClauseId)}
                  onSelect={(keys) => setSelectedClauseId(keys[0] ? Number(keys[0]) : null)}
                />
              ) : (
                <Empty description="No standard clause tree found." />
              )}
            </div>
          </Col>
          <Col xs={24} lg={15}>
            <div className="plan-section-content review-checkpoint-detail">
              {selectedClause ? (
                <ClauseCheckpointPanel
                  clause={selectedClause}
                  checkpoints={selectedCheckpoints}
                  isAdmin={isAdmin}
                  selectedCheckpointId={selectedCheckpointId}
                  loadingDelete={loading.delete}
                  onEdit={(checkpoint) => {
                    setSelectedCheckpointId(checkpoint.id);
                    openEdit(checkpoint);
                  }}
                  onArchive={archive}
                />
              ) : (
                <Empty description="Select a clause" />
              )}
            </div>
          </Col>
        </Row>
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

const ClauseCheckpointPanel = ({
  clause,
  checkpoints,
  isAdmin,
  selectedCheckpointId,
  loadingDelete,
  onEdit,
  onArchive,
}: {
  clause: StandardClause;
  checkpoints: ReviewCheckpoint[];
  isAdmin: boolean;
  selectedCheckpointId: number | null;
  loadingDelete: boolean;
  onEdit: (checkpoint: ReviewCheckpoint) => void;
  onArchive: (checkpoint: ReviewCheckpoint) => void;
}) => (
  <Space direction="vertical" size={16} style={{ width: "100%" }}>
    <div>
      <Space size={8} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {clause.title || clause.clause_no || `Clause #${clause.id}`}
        </Typography.Title>
        {clause.clause_no ? <Tag>{clause.clause_no}</Tag> : null}
        {clause.is_mandatory ? <Tag color="red">mandatory</Tag> : null}
        <Tag color={checkpoints.length ? "blue" : "default"}>C {checkpoints.length}</Tag>
      </Space>
      <Typography.Text type="secondary">
        level {clause.level} / clause #{clause.id}
      </Typography.Text>
    </div>
    <Tabs
      items={[
        {
          key: "clause",
          label: "Clause",
          children: (
            <Typography.Paragraph className="chapter-profile-text-block">
              {clause.content || "No content found for this clause."}
            </Typography.Paragraph>
          ),
        },
        {
          key: "checkpoints",
          label: `Checkpoints (${checkpoints.length})`,
          children: checkpoints.length ? (
            <CheckpointTable
              checkpoints={checkpoints}
              isAdmin={isAdmin}
              selectedCheckpointId={selectedCheckpointId}
              loadingDelete={loadingDelete}
              onEdit={onEdit}
              onArchive={onArchive}
            />
          ) : (
            <Empty description="No checkpoints for this clause." />
          ),
        },
      ]}
    />
  </Space>
);

const CheckpointTable = ({
  checkpoints,
  isAdmin,
  selectedCheckpointId,
  loadingDelete,
  onEdit,
  onArchive,
}: {
  checkpoints: ReviewCheckpoint[];
  isAdmin: boolean;
  selectedCheckpointId: number | null;
  loadingDelete: boolean;
  onEdit: (checkpoint: ReviewCheckpoint) => void;
  onArchive: (checkpoint: ReviewCheckpoint) => void;
}) => (
  <Table<ReviewCheckpoint>
    rowKey="id"
    size="small"
    dataSource={checkpoints}
    pagination={{ pageSize: 8 }}
    onRow={(record) => ({
      onClick: () => onEdit(record),
      className: `document-row${selectedCheckpointId === record.id ? " document-row-selected" : ""}`,
    })}
    columns={[
      { title: "Code", dataIndex: "checkpoint_code", width: 130, ellipsis: true },
      { title: "Checkpoint", dataIndex: "checkpoint_name", ellipsis: true },
      { title: "Type", dataIndex: "checkpoint_type", width: 180 },
      { title: "Risk", dataIndex: "risk_level", width: 100, render: (value: string) => <RiskTag risk={value} /> },
      { title: "Status", dataIndex: "status", width: 110, render: (value: string) => <StatusTag status={value} /> },
      {
        title: "Targets",
        dataIndex: "target_objects",
        width: 180,
        render: (values: string[]) => <TagList values={values} />,
      },
      ...(isAdmin
        ? [
            {
              title: "Actions",
              width: 120,
              render: (_: unknown, record: ReviewCheckpoint) => (
                <Space size={6} wrap onClick={(event) => event.stopPropagation()}>
                  <Popconfirm
                    title="Archive this checkpoint?"
                    okText="Archive"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => onArchive(record)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} loading={loadingDelete}>
                      Archive
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            } as const,
          ]
        : []),
    ]}
    expandable={{
      expandedRowRender: (record) => (
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="Goal">{record.check_goal || "-"}</Descriptions.Item>
          <Descriptions.Item label="Method">{record.check_method || "-"}</Descriptions.Item>
          <Descriptions.Item label="Parameters">
            <TagList values={record.target_parameters} />
          </Descriptions.Item>
          <Descriptions.Item label="Keywords">
            <TagList values={record.keywords} />
          </Descriptions.Item>
          <Descriptions.Item label="Expected">
            <TagList values={record.expected_items} />
          </Descriptions.Item>
          <Descriptions.Item label="Forbidden">
            <TagList values={record.forbidden_items} />
          </Descriptions.Item>
        </Descriptions>
      ),
    }}
  />
);

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

const toClauseTreeData = (
  clauses: StandardClause[],
  checkpointsByClauseId: Map<number, ReviewCheckpoint[]>,
): DataNode[] => {
  const childrenByParentId = new Map<number | null, StandardClause[]>();
  for (const clause of clauses) {
    const siblings = childrenByParentId.get(clause.parent_id) ?? [];
    siblings.push(clause);
    childrenByParentId.set(clause.parent_id, siblings);
  }

  const clauseIds = new Set(clauses.map((clause) => clause.id));
  const roots = clauses.filter((clause) => !clause.parent_id || !clauseIds.has(clause.parent_id));
  return roots.map((clause) => toClauseNode(clause, childrenByParentId, checkpointsByClauseId));
};

const toClauseNode = (
  clause: StandardClause,
  childrenByParentId: Map<number | null, StandardClause[]>,
  checkpointsByClauseId: Map<number, ReviewCheckpoint[]>,
): DataNode => {
  const checkpointCount = checkpointsByClauseId.get(clause.id)?.length ?? 0;
  const label = clause.title || clause.clause_no || `Clause #${clause.id}`;
  return {
    key: String(clause.id),
    title: (
      <Space size={6} wrap>
        <span>{label}</span>
        {checkpointCount ? <Tag color="blue">C {checkpointCount}</Tag> : null}
        {clause.is_mandatory ? <Tag color="red">mandatory</Tag> : null}
      </Space>
    ),
    children: (childrenByParentId.get(clause.id) ?? []).map((child) =>
      toClauseNode(child, childrenByParentId, checkpointsByClauseId),
    ),
  };
};

const groupCheckpointsByClauseId = (checkpoints: ReviewCheckpoint[]) => {
  const grouped = new Map<number, ReviewCheckpoint[]>();
  for (const checkpoint of checkpoints) {
    if (checkpoint.clause_id != null) {
      grouped.set(checkpoint.clause_id, [...(grouped.get(checkpoint.clause_id) ?? []), checkpoint]);
    }
  }
  return grouped;
};

const findFirstCheckpointClauseId = (checkpoints: ReviewCheckpoint[]) =>
  checkpoints.find((checkpoint) => checkpoint.clause_id != null)?.clause_id ?? null;

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
