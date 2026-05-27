import { useEffect, useMemo, useState } from "react";
import type { Key } from "react";
import { useGetIdentity } from "@refinedev/core";
import {
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Tree,
  Typography,
  message,
} from "antd";
import type { Dayjs } from "dayjs";
import type { TablePaginationConfig } from "antd";
import type { DataNode } from "antd/es/tree";
import { ImportOutlined, ReloadOutlined, RobotOutlined, SearchOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  createCheckpointGenerationJob,
  getReviewCheckpointTree,
  listCheckpointGenerationItems,
  listCheckpointGenerationJobs,
  type CheckpointGenerationItem,
  type CheckpointGenerationJob,
  type CheckpointGenerationJobQuery,
  type ReviewCheckpoint,
  type ReviewCheckpointTreeResult,
} from "../services/reviewCheckpointService";
import {
  importStandardFromDocument,
  listStandards,
  type ImportStandardRequest,
  type StandardClause,
  type StandardDocument,
} from "../services/standardService";
import { listPPOcrPdfJobs, type PPOcrPdfJob } from "../services/utilsService";

type FilterValues = {
  status?: string;
};

type ImportStandardFormValues = Omit<ImportStandardRequest, "effective_date"> & {
  effective_date?: Dayjs | null;
};

export const CheckpointGenerationJobsPage = () => {
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [standards, setStandards] = useState<StandardDocument[]>([]);
  const [selectedStandardId, setSelectedStandardId] = useState<number | null>(null);
  const [standardTree, setStandardTree] = useState<ReviewCheckpointTreeResult | null>(null);
  const [generationItems, setGenerationItems] = useState<CheckpointGenerationItem[]>([]);
  const [jobs, setJobs] = useState<CheckpointGenerationJob[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobQuery, setJobQuery] = useState<CheckpointGenerationJobQuery>({ page: 1, page_size: 10 });
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedClauseId, setSelectedClauseId] = useState<number | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [parseJobs, setParseJobs] = useState<PPOcrPdfJob[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [useLlm, setUseLlm] = useState(true);
  const [loading, setLoading] = useState({
    standards: false,
    workspace: false,
    jobs: false,
    queue: false,
    import: false,
    parseJobs: false,
  });
  const [form] = Form.useForm<FilterValues>();
  const [importForm] = Form.useForm<ImportStandardFormValues>();

  const loadStandards = async (nextSelectedId = selectedStandardId) => {
    setLoading((current) => ({ ...current, standards: true }));
    try {
      const result = await listStandards();
      setStandards(result.items);
      const nextId = nextSelectedId && result.items.some((standard) => standard.id === nextSelectedId)
        ? nextSelectedId
        : result.items[0]?.id ?? null;
      setSelectedStandardId(nextId);
      if (nextId) {
        await loadStandardWorkspace(nextId, { standard_id: nextId, page: 1, page_size: jobQuery.page_size ?? 10 }, false);
      }
    } catch {
      message.error("Failed to load standards.");
    } finally {
      setLoading((current) => ({ ...current, standards: false }));
    }
  };

  const loadStandardWorkspace = async (
    standardId: number,
    nextJobQuery: CheckpointGenerationJobQuery = { ...jobQuery, standard_id: standardId },
    preserveJobSelection = true,
  ) => {
    setLoading((current) => ({ ...current, workspace: true, jobs: true }));
    try {
      const [tree, itemResult, jobResult] = await Promise.all([
        getReviewCheckpointTree({ standard_id: standardId }),
        listAllCheckpointGenerationItems(standardId),
        listCheckpointGenerationJobs(nextJobQuery),
      ]);
      setStandardTree(tree);
      setGenerationItems(itemResult);
      setJobs(jobResult.items);
      setJobTotal(jobResult.total);
      setJobQuery({ ...nextJobQuery, standard_id: standardId, page: jobResult.page, page_size: jobResult.page_size });
      const nextJobId =
        preserveJobSelection && selectedJobId && jobResult.items.some((job) => job.id === selectedJobId)
          ? selectedJobId
          : jobResult.items[0]?.id ?? null;
      setSelectedJobId(nextJobId);
      setSelectedClauseId((current) => current ?? findFirstUnfinishedClauseId(tree.clauses, tree.checkpoints, itemResult) ?? tree.clauses[0]?.id ?? null);
    } catch {
      message.error("Failed to load checkpoint generation workspace.");
    } finally {
      setLoading((current) => ({ ...current, workspace: false, jobs: false }));
    }
  };

  useEffect(() => {
    void loadStandards();
  }, []);

  const selectStandard = async (standardId: number) => {
    setSelectedStandardId(standardId);
    setSelectedClauseId(null);
    setSelectedRowKeys([]);
    setSelectedJobId(null);
    form.resetFields();
    await loadStandardWorkspace(standardId, { standard_id: standardId, page: 1, page_size: jobQuery.page_size ?? 10 }, false);
  };

  const applyFilter = async () => {
    if (!selectedStandardId) {
      return;
    }
    const values = form.getFieldsValue();
    await loadStandardWorkspace(
      selectedStandardId,
      { ...values, standard_id: selectedStandardId, page: 1, page_size: jobQuery.page_size ?? 10 },
      false,
    );
  };

  const refresh = async () => {
    if (selectedStandardId) {
      await loadStandardWorkspace(selectedStandardId);
    } else {
      await loadStandards();
    }
  };

  const queueClauses = async (clauseIds: number[]) => {
    if (!selectedStandardId || !clauseIds.length) {
      message.warning("Select clauses first.");
      return;
    }
    setLoading((current) => ({ ...current, queue: true }));
    try {
      const job = await createCheckpointGenerationJob({ standard_id: selectedStandardId, clause_ids: clauseIds, use_llm: useLlm });
      message.success(`Checkpoint generation job #${job.id} queued.`);
      setSelectedRowKeys([]);
      setSelectedJobId(job.id);
      await loadStandardWorkspace(selectedStandardId, { ...jobQuery, standard_id: selectedStandardId, page: 1 }, false);
    } catch {
      message.error("Failed to submit checkpoint generation job.");
    } finally {
      setLoading((current) => ({ ...current, queue: false }));
    }
  };

  const queueSelectedClauses = async () => {
    await queueClauses(selectedRowKeys.map((key) => Number(key)));
  };

  const openImport = async () => {
    importForm.resetFields();
    setImportOpen(true);
    setLoading((current) => ({ ...current, parseJobs: true }));
    try {
      const jobs = await listPPOcrPdfJobs();
      setParseJobs(jobs.filter((job) => job.parse_result_id));
    } catch {
      message.error("Failed to load parsed PDF jobs.");
    } finally {
      setLoading((current) => ({ ...current, parseJobs: false }));
    }
  };

  const submitImport = async () => {
    const values = await importForm.validateFields();
    setLoading((current) => ({ ...current, import: true }));
    try {
      const result = await importStandardFromDocument({
        ...values,
        effective_date: values.effective_date ? values.effective_date.format("YYYY-MM-DD") : null,
      });
      message.success(`Imported standard ${result.standard_id}, ${result.clause_count} clauses generated.`);
      setImportOpen(false);
      importForm.resetFields();
      await loadStandards(result.standard_id);
    } catch {
      message.error("Failed to import standard.");
    } finally {
      setLoading((current) => ({ ...current, import: false }));
    }
  };

  const handleParseResultSelect = (parseResultId?: number | null) => {
    if (!parseResultId) {
      return;
    }
    const selected = parseJobs.find((job) => job.parse_result_id === parseResultId);
    if (selected && !importForm.getFieldValue("standard_name")) {
      importForm.setFieldValue("standard_name", stripExtension(selected.file_name));
    }
  };

  const itemsByClauseId = useMemo(() => groupItemsByClauseId(generationItems), [generationItems]);
  const checkpointsByClauseId = useMemo(
    () => groupCheckpointsByClauseId(standardTree?.checkpoints ?? []),
    [standardTree],
  );
  const selectedClause = useMemo(
    () => (standardTree && selectedClauseId ? standardTree.clauses.find((clause) => clause.id === selectedClauseId) ?? null : null),
    [standardTree, selectedClauseId],
  );
  const selectedItem = selectedClause ? itemsByClauseId.get(selectedClause.id) ?? null : null;
  const selectedCheckpoints = selectedClause ? checkpointsByClauseId.get(selectedClause.id) ?? [] : [];
  const ungeneratedClauseIds = useMemo(
    () => findQueueableClauseIds(standardTree?.clauses ?? [], checkpointsByClauseId, itemsByClauseId),
    [standardTree, checkpointsByClauseId, itemsByClauseId],
  );

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Checkpoint Generation</h1>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading.standards || loading.workspace || loading.jobs} onClick={() => void refresh()}>
            Refresh
          </Button>
          {isAdmin ? (
            <Button type="primary" icon={<ImportOutlined />} onClick={() => void openImport()}>
              Import Standard
            </Button>
          ) : null}
        </Space>
      </div>

      <Card title="Standards">
        <Table<StandardDocument>
          rowKey="id"
          size="small"
          loading={loading.standards}
          dataSource={standards}
          pagination={{ pageSize: 6 }}
          onRow={(record) => ({
            onClick: () => void selectStandard(record.id),
            className: `document-row${selectedStandardId === record.id ? " document-row-selected" : ""}`,
          })}
          columns={[
            { title: "Code", dataIndex: "standard_code", width: 150 },
            { title: "Name", dataIndex: "standard_name", ellipsis: true },
            { title: "Type", dataIndex: "standard_type", width: 110 },
            { title: "Version", dataIndex: "version", width: 100 },
            { title: "Status", dataIndex: "status", width: 110, render: (value: string) => <Tag>{value}</Tag> },
          ]}
        />
      </Card>

      <Card>
        <Form form={form} layout="inline" className="table-filter-form">
          <Form.Item name="status" label="Job Status">
            <Select allowClear style={{ width: 170 }} options={generationStatusOptions} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} disabled={!selectedStandardId} onClick={() => void applyFilter()}>
              Search Jobs
            </Button>
          </Form.Item>
          <Form.Item>
            <Checkbox checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)}>
              使用 LLM
            </Checkbox>
          </Form.Item>
          <Form.Item>
            <Tooltip title={getGenerateTooltip(isAdmin, selectedRowKeys.length)}>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={loading.queue}
                disabled={!isAdmin || !selectedRowKeys.length}
                onClick={() => void queueSelectedClauses()}
              >
                Add Selected to Queue
              </Button>
            </Tooltip>
          </Form.Item>
          <Form.Item>
            <Tooltip title={getGenerateTooltip(isAdmin, ungeneratedClauseIds.length)}>
              <Button
                icon={<RobotOutlined />}
                loading={loading.queue}
                disabled={!isAdmin || !ungeneratedClauseIds.length}
                onClick={() => void queueClauses(ungeneratedClauseIds)}
              >
                Queue All Ungenerated
              </Button>
            </Tooltip>
          </Form.Item>
        </Form>
      </Card>

      <Card title="Generation Jobs">
        <Table<CheckpointGenerationJob>
          rowKey="id"
          size="small"
          loading={loading.jobs}
          dataSource={jobs}
          onRow={(record) => ({
            onClick: () => setSelectedJobId(record.id),
            className: `document-row${selectedJobId === record.id ? " document-row-selected" : ""}`,
          })}
          pagination={{
            current: jobQuery.page,
            pageSize: jobQuery.page_size,
            total: jobTotal,
            showSizeChanger: true,
          }}
          onChange={(pagination: TablePaginationConfig) =>
            selectedStandardId
              ? void loadStandardWorkspace(selectedStandardId, {
                  ...jobQuery,
                  page: pagination.current ?? 1,
                  page_size: pagination.pageSize ?? 10,
                })
              : undefined
          }
          columns={[
            { title: "Job ID", dataIndex: "id", width: 90 },
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
        title={standardTree?.standard ? `Clause Tree - ${standardTree.standard.standard_name}` : "Clause Tree"}
        loading={loading.workspace}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={9}>
            <div className="plan-section-tree checkpoint-generation-tree">
              {standardTree?.clauses.length ? (
                <Tree
                  blockNode
                  defaultExpandAll
                  checkable={isAdmin}
                  checkedKeys={selectedRowKeys}
                  selectedKeys={selectedClauseId ? [String(selectedClauseId)] : []}
                  treeData={toClauseTreeData(standardTree.clauses, itemsByClauseId, checkpointsByClauseId)}
                  onCheck={(keys) => setSelectedRowKeys(Array.isArray(keys) ? keys : keys.checked)}
                  onSelect={(keys) => setSelectedClauseId(keys[0] ? Number(keys[0]) : null)}
                />
              ) : (
                <Empty description="Select a standard to view clauses." />
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
                  isAdmin={isAdmin}
                  loading={loading.queue}
                  onQueue={() => void queueClauses([selectedClause.id])}
                />
              ) : (
                <Empty description="Select a clause" />
              )}
            </div>
          </Col>
        </Row>
      </Card>

      <Modal
        title="Import Standard"
        open={importOpen}
        width={720}
        confirmLoading={loading.import}
        onOk={() => void submitImport()}
        onCancel={() => setImportOpen(false)}
      >
        <Form form={importForm} layout="vertical" requiredMark={false}>
          <Form.Item name="document_id" label="Parsed Document" rules={[{ required: true }]}>
            <Select
              showSearch
              loading={loading.parseJobs}
              optionFilterProp="label"
              onChange={handleParseResultSelect}
              options={parseJobs.map((job) => ({
                value: job.parse_result_id ?? undefined,
                label: `${job.file_name} · result #${job.parse_result_id}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="standard_name" label="Standard Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space align="start" style={{ width: "100%" }} className="form-space-row">
            <Form.Item name="standard_code" label="Code" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="standard_type" label="Type" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
          </Space>
          <Space align="start" style={{ width: "100%" }} className="form-space-row">
            <Form.Item name="version" label="Version" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="effective_date" label="Effective Date" style={{ flex: 1 }}>
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const ClauseCheckpointPanel = ({
  clause,
  generationItem,
  checkpoints,
  isAdmin,
  loading,
  onQueue,
}: {
  clause: StandardClause;
  generationItem: CheckpointGenerationItem | null;
  checkpoints: ReviewCheckpoint[];
  isAdmin: boolean;
  loading: boolean;
  onQueue: () => void;
}) => {
  const canQueue = isAdmin && !checkpoints.length && !isInFlight(generationItem);
  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div>
        <Space size={8} wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {clause.title || clause.clause_no || `Clause #${clause.id}`}
          </Typography.Title>
          {clause.clause_no ? <Tag>{clause.clause_no}</Tag> : null}
          {clause.is_mandatory ? <Tag color="red">mandatory</Tag> : null}
          {checkpoints.length ? <Tag color="blue">generated {checkpoints.length}</Tag> : <Tag>not generated</Tag>}
          {generationItem ? <GenerationStatusTag status={generationItem.status} /> : null}
        </Space>
        <Typography.Text type="secondary">
          level {clause.level} / clause #{clause.id}
        </Typography.Text>
      </div>
      {canQueue ? (
        <Button type="primary" icon={<RobotOutlined />} loading={loading} onClick={onQueue}>
          Add This Clause to Queue
        </Button>
      ) : null}
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
                <Descriptions.Item label="Job ID">{generationItem.job_id}</Descriptions.Item>
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
              <Empty description="This clause has no generation record yet." />
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
};

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

const listAllCheckpointGenerationItems = async (standardId: number) => {
  const pageSize = 200;
  const first = await listCheckpointGenerationItems({ standard_id: standardId, page: 1, page_size: pageSize });
  const items = [...first.items];
  for (let page = 2; items.length < first.total; page += 1) {
    const next = await listCheckpointGenerationItems({ standard_id: standardId, page, page_size: pageSize });
    items.push(...next.items);
  }
  return items;
};

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
        {checkpointCount ? <Tag color="blue">C {checkpointCount}</Tag> : <Tag>empty</Tag>}
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
    if (item.clause_id != null && !grouped.has(item.clause_id)) {
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

const findFirstUnfinishedClauseId = (
  clauses: StandardClause[],
  checkpoints: ReviewCheckpoint[],
  items: CheckpointGenerationItem[],
) => {
  const checkpointsByClauseId = groupCheckpointsByClauseId(checkpoints);
  const itemsByClauseId = groupItemsByClauseId(items);
  return clauses.find((clause) => !checkpointsByClauseId.get(clause.id)?.length && !isInFlight(itemsByClauseId.get(clause.id)))?.id ?? null;
};

const findQueueableClauseIds = (
  clauses: StandardClause[],
  checkpointsByClauseId: Map<number, ReviewCheckpoint[]>,
  itemsByClauseId: Map<number, CheckpointGenerationItem>,
) => clauses
  .filter((clause) => !checkpointsByClauseId.get(clause.id)?.length && !isInFlight(itemsByClauseId.get(clause.id)))
  .map((clause) => clause.id);

const isInFlight = (item?: CheckpointGenerationItem | null) => item?.status === "queued" || item?.status === "running";

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

const getGenerateTooltip = (isAdmin: boolean, selectedCount: number) => {
  if (!isAdmin) {
    return "只有 admin 可以生成审查点";
  }
  if (!selectedCount) {
    return "没有可加入队列的条文";
  }
  return `将 ${selectedCount} 条条文加入生成队列`;
};

const stripExtension = (value: string) => value.replace(/\.[^.]+$/, "");
