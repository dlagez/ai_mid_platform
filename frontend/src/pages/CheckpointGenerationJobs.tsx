import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  InputNumber,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tree,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import type { DataNode } from "antd/es/tree";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import {
  getCheckpointGenerationTree,
  listCheckpointGenerationJobs,
  type CheckpointGenerationItem,
  type CheckpointGenerationJob,
  type CheckpointGenerationJobQuery,
  type CheckpointGenerationTreeResult,
  type ReviewCheckpoint,
} from "../services/reviewCheckpointService";
import type { StandardClause } from "../services/standardService";

type FilterValues = {
  standard_id?: number;
  status?: string;
};

export const CheckpointGenerationJobsPage = () => {
  const [jobs, setJobs] = useState<CheckpointGenerationJob[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobQuery, setJobQuery] = useState<CheckpointGenerationJobQuery>({ page: 1, page_size: 10 });
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [generationTree, setGenerationTree] = useState<CheckpointGenerationTreeResult | null>(null);
  const [selectedClauseId, setSelectedClauseId] = useState<number | null>(null);
  const [loading, setLoading] = useState({ jobs: false, tree: false });
  const [form] = Form.useForm<FilterValues>();

  const loadJobs = async (nextQuery = jobQuery, preserveSelection = true) => {
    setLoading((current) => ({ ...current, jobs: true }));
    try {
      const result = await listCheckpointGenerationJobs(nextQuery);
      setJobs(result.items);
      setJobTotal(result.total);
      setJobQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
      const nextSelectedId = preserveSelection && selectedJobId && result.items.some((job) => job.id === selectedJobId)
        ? selectedJobId
        : result.items[0]?.id ?? null;
      setSelectedJobId(nextSelectedId);
      if (nextSelectedId) {
        await loadGenerationTree(nextSelectedId);
      } else {
        setGenerationTree(null);
        setSelectedClauseId(null);
      }
    } catch {
      message.error("Failed to load checkpoint generation jobs.");
    } finally {
      setLoading((current) => ({ ...current, jobs: false }));
    }
  };

  const loadGenerationTree = async (jobId: number) => {
    setLoading((current) => ({ ...current, tree: true }));
    try {
      const result = await getCheckpointGenerationTree(jobId);
      setGenerationTree(result);
      setSelectedClauseId((current) => current ?? findFirstGeneratedClauseId(result.items) ?? result.clauses[0]?.id ?? null);
    } catch {
      message.error("Failed to load checkpoint generation tree.");
    } finally {
      setLoading((current) => ({ ...current, tree: false }));
    }
  };

  useEffect(() => {
    void loadJobs();
  }, []);

  const applyFilter = async () => {
    const values = form.getFieldsValue();
    setSelectedJobId(null);
    setSelectedClauseId(null);
    await loadJobs({ ...values, page: 1, page_size: jobQuery.page_size ?? 10 }, false);
  };

  const refresh = async () => {
    await loadJobs();
  };

  const selectJob = async (job: CheckpointGenerationJob) => {
    setSelectedJobId(job.id);
    setSelectedClauseId(null);
    await loadGenerationTree(job.id);
  };

  const itemsByClauseId = useMemo(() => groupItemsByClauseId(generationTree?.items ?? []), [generationTree]);
  const checkpointsByClauseId = useMemo(
    () => groupCheckpointsByClauseId(generationTree?.checkpoints ?? []),
    [generationTree],
  );
  const selectedClause = useMemo(
    () => (generationTree && selectedClauseId ? generationTree.clauses.find((clause) => clause.id === selectedClauseId) ?? null : null),
    [generationTree, selectedClauseId],
  );
  const selectedItem = selectedClause ? itemsByClauseId.get(selectedClause.id) ?? null : null;
  const selectedCheckpoints = selectedClause ? checkpointsByClauseId.get(selectedClause.id) ?? [] : [];

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Checkpoint Generation</h1>
        <Button icon={<ReloadOutlined />} loading={loading.jobs || loading.tree} onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      <Card>
        <Form form={form} layout="inline" className="table-filter-form">
          <Form.Item name="standard_id" label="Standard ID">
            <InputNumber min={1} precision={0} />
          </Form.Item>
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 170 }} options={generationStatusOptions} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="Generation Jobs">
        <Table<CheckpointGenerationJob>
          rowKey="id"
          loading={loading.jobs}
          dataSource={jobs}
          onRow={(record) => ({
            onClick: () => void selectJob(record),
            className: `document-row${selectedJobId === record.id ? " document-row-selected" : ""}`,
          })}
          pagination={{
            current: jobQuery.page,
            pageSize: jobQuery.page_size,
            total: jobTotal,
            showSizeChanger: true,
          }}
          onChange={(pagination: TablePaginationConfig) =>
            void loadJobs({
              ...jobQuery,
              page: pagination.current ?? 1,
              page_size: pagination.pageSize ?? 10,
            })
          }
          columns={[
            { title: "Job ID", dataIndex: "id", width: 90 },
            { title: "Standard ID", dataIndex: "standard_id", width: 120 },
            {
              title: "Progress",
              width: 230,
              render: (_, record) => (
                <Progress
                  percent={progressPercent(record)}
                  size="small"
                  status={record.status === "failed" ? "exception" : record.status === "running" ? "active" : "normal"}
                />
              ),
            },
            { title: "Created", dataIndex: "created_count", width: 100 },
            { title: "Failed", dataIndex: "failed_count", width: 90 },
            { title: "Skipped", dataIndex: "skipped_count", width: 90 },
            {
              title: "Status",
              dataIndex: "status",
              width: 140,
              render: (value: string) => <GenerationStatusTag status={value} />,
            },
            { title: "Created At", dataIndex: "created_at", width: 190, render: formatTime },
            {
              title: "Message",
              dataIndex: "error_message",
              ellipsis: true,
              render: (value: string | null) => value || "-",
            },
          ]}
        />
      </Card>

      <Card
        title={
          generationTree?.standard
            ? `Clause Tree - ${generationTree.standard.standard_name}`
            : "Clause Tree"
        }
        loading={loading.tree}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={9}>
            <div className="plan-section-tree checkpoint-generation-tree">
              {generationTree?.clauses.length ? (
                <Tree
                  blockNode
                  defaultExpandAll
                  selectedKeys={selectedClauseId ? [String(selectedClauseId)] : []}
                  treeData={toClauseTreeData(generationTree.clauses, itemsByClauseId, checkpointsByClauseId)}
                  onSelect={(keys) => setSelectedClauseId(keys[0] ? Number(keys[0]) : null)}
                />
              ) : (
                <Empty description="No clause tree found." />
              )}
            </div>
          </Col>
          <Col xs={24} lg={15}>
            <div className="plan-section-content checkpoint-generation-detail">
              {selectedClause ? (
                <ClauseCheckpointPanel
                  clause={selectedClause}
                  generationItem={selectedItem}
                  checkpoints={selectedCheckpoints}
                />
              ) : (
                <Empty description="Select a clause" />
              )}
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  );
};

const ClauseCheckpointPanel = ({
  clause,
  generationItem,
  checkpoints,
}: {
  clause: StandardClause;
  generationItem: CheckpointGenerationItem | null;
  checkpoints: ReviewCheckpoint[];
}) => (
  <Space direction="vertical" size={16} style={{ width: "100%" }}>
    <div>
      <Space size={8} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {clause.title || clause.clause_no || `Clause #${clause.id}`}
        </Typography.Title>
        {clause.clause_no ? <Tag>{clause.clause_no}</Tag> : null}
        {clause.is_mandatory ? <Tag color="red">mandatory</Tag> : null}
        {generationItem ? <GenerationStatusTag status={generationItem.status} /> : null}
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
          key: "generation",
          label: "Generation",
          children: generationItem ? (
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="Item ID">{generationItem.id}</Descriptions.Item>
              <Descriptions.Item label="Status">
                <GenerationStatusTag status={generationItem.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Created">{generationItem.created_count}</Descriptions.Item>
              <Descriptions.Item label="Checkpoint IDs">
                <IdList values={generationItem.checkpoint_ids} />
              </Descriptions.Item>
              <Descriptions.Item label="Message" span={2}>
                {generationItem.message || "-"}
              </Descriptions.Item>
              <Descriptions.Item label="Started At">{formatTime(generationItem.started_at)}</Descriptions.Item>
              <Descriptions.Item label="Finished At">{formatTime(generationItem.finished_at)}</Descriptions.Item>
            </Descriptions>
          ) : (
            <Empty description="This clause was not included in the selected generation job." />
          ),
        },
        {
          key: "checkpoints",
          label: `Checkpoints (${checkpoints.length})`,
          children: checkpoints.length ? <CheckpointTable checkpoints={checkpoints} /> : <Empty description="No checkpoints generated for this clause." />,
        },
      ]}
    />
  </Space>
);

const CheckpointTable = ({ checkpoints }: { checkpoints: ReviewCheckpoint[] }) => (
  <Table<ReviewCheckpoint>
    rowKey="id"
    size="small"
    dataSource={checkpoints}
    pagination={{ pageSize: 8 }}
    columns={[
      { title: "Code", dataIndex: "checkpoint_code", width: 130, ellipsis: true },
      { title: "Checkpoint", dataIndex: "checkpoint_name", ellipsis: true },
      { title: "Type", dataIndex: "checkpoint_type", width: 180 },
      { title: "Risk", dataIndex: "risk_level", width: 100, render: (value: string) => <RiskTag risk={value} /> },
      { title: "Status", dataIndex: "status", width: 110, render: (value: string) => <Tag>{value}</Tag> },
      {
        title: "Targets",
        dataIndex: "target_objects",
        width: 180,
        render: (values: string[]) => <TagList values={values} />,
      },
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
        </Descriptions>
      ),
    }}
  />
);

const generationStatusOptions = [
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "success", label: "Success" },
  { value: "partial_success", label: "Partial Success" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

const progressPercent = (job: CheckpointGenerationJob) => {
  if (!job.total_clauses) {
    return 0;
  }
  return Math.round((job.processed_clauses / job.total_clauses) * 100);
};

const formatTime = (value?: string | null) => (value ? new Date(value).toLocaleString() : "-");

const toClauseTreeData = (
  clauses: StandardClause[],
  itemsByClauseId: Map<number, CheckpointGenerationItem>,
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
  return roots.map((clause) => toClauseNode(clause, childrenByParentId, itemsByClauseId, checkpointsByClauseId));
};

const toClauseNode = (
  clause: StandardClause,
  childrenByParentId: Map<number | null, StandardClause[]>,
  itemsByClauseId: Map<number, CheckpointGenerationItem>,
  checkpointsByClauseId: Map<number, ReviewCheckpoint[]>,
): DataNode => {
  const item = itemsByClauseId.get(clause.id);
  const checkpointCount = checkpointsByClauseId.get(clause.id)?.length ?? 0;
  const label = clause.title || clause.clause_no || `Clause #${clause.id}`;
  return {
    key: String(clause.id),
    title: (
      <Space size={6} wrap>
        <span>{label}</span>
        {checkpointCount ? <Tag color="blue">C {checkpointCount}</Tag> : null}
        {item ? <GenerationStatusTag status={item.status} /> : null}
      </Space>
    ),
    children: (childrenByParentId.get(clause.id) ?? []).map((child) =>
      toClauseNode(child, childrenByParentId, itemsByClauseId, checkpointsByClauseId),
    ),
  };
};

const groupItemsByClauseId = (items: CheckpointGenerationItem[]) => {
  const grouped = new Map<number, CheckpointGenerationItem>();
  for (const item of items) {
    if (item.clause_id != null) {
      grouped.set(item.clause_id, item);
    }
  }
  return grouped;
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

const findFirstGeneratedClauseId = (items: CheckpointGenerationItem[]) =>
  items.find((item) => item.clause_id != null)?.clause_id ?? null;

const IdList = ({ values }: { values: number[] }) => {
  if (!values?.length) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  return (
    <Space size={4} wrap>
      {values.map((value) => (
        <Tag key={value}>{value}</Tag>
      ))}
    </Space>
  );
};

const TagList = ({ values }: { values?: string[] }) => {
  if (!values?.length) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  return (
    <Space size={4} wrap>
      {values.slice(0, 5).map((value) => (
        <Tag key={value}>{value}</Tag>
      ))}
      {values.length > 5 ? <Typography.Text type="secondary">+{values.length - 5}</Typography.Text> : null}
    </Space>
  );
};

const RiskTag = ({ risk }: { risk: string }) => {
  const color = risk === "critical" ? "red" : risk === "major" ? "orange" : risk === "minor" ? "blue" : "default";
  return <Tag color={color}>{risk || "-"}</Tag>;
};

const GenerationStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success"
      ? "green"
      : status === "partial_success" || status === "skipped"
        ? "gold"
        : status === "failed"
          ? "red"
          : status === "running"
            ? "blue"
            : "default";
  return <Tag color={color}>{status}</Tag>;
};
