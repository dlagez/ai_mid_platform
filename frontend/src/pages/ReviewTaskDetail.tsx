import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  NodeIndexOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { Button, Card, Descriptions, Space, Table, Tag, Typography, message } from "antd";
import type { TablePaginationConfig } from "antd";
import {
  buildChapterProfiles,
  getReviewTask,
  listReviewTaskCheckpointMatches,
  matchReviewCheckpoints,
  runCheckpointReview,
  type CheckpointMatchListQuery,
  type CheckpointMatchWithCheckpoint,
  type ReviewTask,
} from "../services/reviewTaskService";
import { getDocumentSections, type PlanSection } from "../services/documentService";

export const ReviewTaskDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const taskId = Number(id);
  const [task, setTask] = useState<ReviewTask | null>(null);
  const [matches, setMatches] = useState<CheckpointMatchWithCheckpoint[]>([]);
  const [sectionById, setSectionById] = useState<Map<number, PlanSection>>(new Map());
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<CheckpointMatchListQuery>({ matched_only: true, page: 1, page_size: 20 });
  const [loading, setLoading] = useState({
    task: false,
    matches: false,
    profiles: false,
    match: false,
    run: false,
    sections: false,
  });

  const loadTask = async () => {
    if (!taskId) {
      return;
    }
    setLoading((current) => ({ ...current, task: true }));
    try {
      setTask(await getReviewTask(taskId));
    } catch {
      message.error("Failed to load review task.");
    } finally {
      setLoading((current) => ({ ...current, task: false }));
    }
  };

  const loadMatches = async (nextQuery = query) => {
    if (!taskId) {
      return;
    }
    setLoading((current) => ({ ...current, matches: true }));
    try {
      const result = await listReviewTaskCheckpointMatches(taskId, nextQuery);
      setMatches(result.items);
      setTotal(result.total);
      setQuery({
        ...nextQuery,
        page: result.page ?? nextQuery.page,
        page_size: result.page_size ?? nextQuery.page_size,
      });
    } catch {
      message.error("Failed to load checkpoint matches.");
    } finally {
      setLoading((current) => ({ ...current, matches: false }));
    }
  };

  const loadSections = async (documentId: number) => {
    setLoading((current) => ({ ...current, sections: true }));
    try {
      const result = await getDocumentSections(documentId);
      setSectionById(flattenSections(result.sections));
    } catch {
      message.error("Failed to load plan sections.");
    } finally {
      setLoading((current) => ({ ...current, sections: false }));
    }
  };

  const refresh = async () => {
    const nextTask = taskId ? await getReviewTask(taskId).catch(() => null) : null;
    if (!nextTask) {
      message.error("Failed to load review task.");
      return;
    }
    setTask(nextTask);
    await Promise.all([loadSections(nextTask.plan_document_id), loadMatches()]);
  };

  useEffect(() => {
    if (!taskId) {
      message.error("Invalid review task id.");
      return;
    }
    void refresh();
  }, [taskId]);

  const handleBuildProfiles = async () => {
    setLoading((current) => ({ ...current, profiles: true }));
    try {
      const result = await buildChapterProfiles(taskId);
      message.success(`Profiles saved: ${result.created_count} created, ${result.updated_count} updated.`);
    } catch {
      message.error("Failed to build chapter profiles.");
    } finally {
      setLoading((current) => ({ ...current, profiles: false }));
    }
  };

  const handleMatch = async () => {
    setLoading((current) => ({ ...current, match: true }));
    try {
      const result = await matchReviewCheckpoints(taskId);
      message.success(`Matched ${result.selected_count} selected checkpoints.`);
      await loadMatches({ ...query, page: 1 });
    } catch {
      message.error("Failed to match checkpoints.");
    } finally {
      setLoading((current) => ({ ...current, match: false }));
    }
  };

  const handleRun = async () => {
    setLoading((current) => ({ ...current, run: true }));
    try {
      const result = await runCheckpointReview(taskId);
      message.success(`Executed ${result.executed_count} checkpoint reviews.`);
      await refresh();
    } catch {
      message.error("Failed to run checkpoint review.");
    } finally {
      setLoading((current) => ({ ...current, run: false }));
    }
  };

  const handleTableChange = async (pagination: TablePaginationConfig) => {
    await loadMatches({
      ...query,
      page: pagination.current ?? 1,
      page_size: pagination.pageSize ?? 20,
    });
  };

  return (
    <div className="page">
      <div className="page-heading">
        <Space align="center">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/review-tasks")}>
            Back
          </Button>
          <h1>Review Task Detail</h1>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading.task || loading.matches} onClick={() => void refresh()}>
            Refresh
          </Button>
          <Button icon={<NodeIndexOutlined />} loading={loading.profiles} onClick={() => void handleBuildProfiles()}>
            Build Profiles
          </Button>
          <Button type="primary" icon={<CheckCircleOutlined />} loading={loading.match} onClick={() => void handleMatch()}>
            Match Checkpoints
          </Button>
          <Button icon={<PlayCircleOutlined />} loading={loading.run} onClick={() => void handleRun()}>
            Run Review
          </Button>
        </Space>
      </div>

      <Card loading={loading.task}>
        <Descriptions column={{ xs: 1, sm: 2, lg: 4 }} size="small" bordered>
          <Descriptions.Item label="Task ID">{task?.id ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Task Name">{task?.task_name ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Status">{task ? <StatusTag status={task.status} /> : "-"}</Descriptions.Item>
          <Descriptions.Item label="Mode">{task?.review_mode ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Plan Document ID">{task?.plan_document_id ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Template ID">{task?.template_id ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Work Type">{task?.work_type ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Version">{task ? `v${task.version}` : "-"}</Descriptions.Item>
          <Descriptions.Item label="Issues">{task?.total_issue_count ?? 0}</Descriptions.Item>
          <Descriptions.Item label="Critical">{task?.critical_issue_count ?? 0}</Descriptions.Item>
          <Descriptions.Item label="Major">{task?.major_issue_count ?? 0}</Descriptions.Item>
          <Descriptions.Item label="Minor">{task?.minor_issue_count ?? 0}</Descriptions.Item>
          <Descriptions.Item label="Created At">{formatDateTime(task?.created_at ?? null)}</Descriptions.Item>
          <Descriptions.Item label="Started At">{formatDateTime(task?.started_at ?? null)}</Descriptions.Item>
          <Descriptions.Item label="Finished At">{formatDateTime(task?.finished_at ?? null)}</Descriptions.Item>
          <Descriptions.Item label="Error">{task?.error_message ?? "-"}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title="Checkpoint Matches"
        extra={
          <Space>
            <Button
              size="small"
              type={query.matched_only ? "primary" : "default"}
              onClick={() => void loadMatches({ ...query, matched_only: true, status: undefined, page: 1 })}
            >
              Matched
            </Button>
            <Button
              size="small"
              type={!query.matched_only && !query.status ? "primary" : "default"}
              onClick={() => void loadMatches({ ...query, matched_only: false, status: undefined, page: 1 })}
            >
              All
            </Button>
          </Space>
        }
      >
        <Table<CheckpointMatchWithCheckpoint>
          rowKey="id"
          loading={loading.matches || loading.sections}
          dataSource={matches}
          expandable={{
            expandedRowRender: (record) => (
              <MatchDetailPanel record={record} section={sectionById.get(record.section_id) ?? null} />
            ),
            rowExpandable: () => true,
          }}
          pagination={{
            current: query.page,
            pageSize: query.page_size,
            total,
            showSizeChanger: true,
          }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            {
              title: "Section",
              dataIndex: "section",
              width: 220,
              render: (_, record) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text strong>
                    {sectionById.get(record.section_id)?.title ?? record.section?.title ?? `Section ${record.section_id}`}
                  </Typography.Text>
                  <Typography.Text type="secondary">{record.section?.section_no ?? "-"}</Typography.Text>
                </Space>
              ),
            },
            {
              title: "Checkpoint",
              dataIndex: "checkpoint",
              render: (_, record) => (
                <Space direction="vertical" size={0}>
                  <Typography.Text ellipsis style={{ maxWidth: 520 }}>
                    {record.checkpoint?.rule_text ?? `Checkpoint ${record.checkpoint_id}`}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    {[record.checkpoint?.clause_no, record.checkpoint?.rule_code].filter(Boolean).join(" / ") || "-"}
                  </Typography.Text>
                </Space>
              ),
            },
            {
              title: "Score",
              dataIndex: "match_score",
              width: 100,
              render: (value: number) => value.toFixed(2),
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 120,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Dimensions",
              dataIndex: "match_dimensions",
              width: 240,
              render: (value: Record<string, unknown>) => (
                <Space size={4} wrap>
                  {Object.entries(value || {}).map(([key, item]) => (
                    <Tag key={key}>
                      {key}: {String(item)}
                    </Tag>
                  ))}
                </Space>
              ),
            },
            { title: "Reason", dataIndex: "match_reason", width: 180, ellipsis: true },
          ]}
        />
      </Card>
    </div>
  );
};

const MatchDetailPanel = ({
  record,
  section,
}: {
  record: CheckpointMatchWithCheckpoint;
  section: PlanSection | null;
}) => {
  const sectionTitle = section?.title ?? record.section?.title ?? "";
  const sectionNo = section?.section_no ?? record.section?.section_no ?? "";
  const sectionContent = record.section?.content || section?.content || "";
  const sectionText = [sectionNo, sectionTitle, sectionContent].filter(Boolean).join("\n");
  const checkpointObjects = record.checkpoint?.object_terms ?? [];
  const checkpointContext = [record.checkpoint?.clause_no, record.checkpoint?.rule_code].filter(Boolean) as string[];
  const checkpointText = [record.checkpoint?.rule_text, record.checkpoint?.clause_text].filter(Boolean).join("\n\n");
  const matchedObjects = findMatchedTerms(checkpointObjects, sectionText);
  const matchedContext = findMatchedTerms(checkpointContext, sectionText);
  const highlightTerms = [...matchedObjects, ...matchedContext];

  return (
    <div className="match-detail-panel">
      <div className="match-detail-column">
        <Typography.Title level={5}>Section Text</Typography.Title>
        <div className="match-detail-title">{[sectionNo, sectionTitle].filter(Boolean).join(" ") || "-"}</div>
        <div className="match-detail-text">
          {sectionContent ? <HighlightedText text={sectionContent} terms={highlightTerms} /> : "No content found for this section."}
        </div>
      </div>

      <div className="match-detail-column">
        <Typography.Title level={5}>Checkpoint Text / Objects</Typography.Title>
        <div className="match-object-row">
          {checkpointObjects.length ? (
            checkpointObjects.map((term) => (
              <Tag key={term} color={matchedObjects.includes(term) ? "gold" : "default"}>
                {term}
              </Tag>
            ))
          ) : (
            <Typography.Text type="secondary">No objects</Typography.Text>
          )}
        </div>
        <div className="match-detail-text">
          {checkpointText ? <HighlightedText text={checkpointText} terms={highlightTerms} /> : "No checkpoint text found."}
        </div>
      </div>

      <div className="match-detail-column">
        <Typography.Title level={5}>Matched On</Typography.Title>
        <MatchSignal label="Objects" score={record.match_dimensions?.object_match} values={matchedObjects} />
        <MatchSignal label="Context" score={record.match_dimensions?.context_match} values={matchedContext} />
        <MatchSignal label="Semantic Text" score={record.match_dimensions?.semantic_similarity} values={[]} />
        {record.match_reason ? <div className="match-reason">{record.match_reason}</div> : null}
      </div>
    </div>
  );
};

const MatchSignal = ({
  label,
  score,
  values,
}: {
  label: string;
  score: unknown;
  values: string[];
}) => {
  const rawScore = typeof score === "number" ? score : Number(score ?? 0);
  const numericScore = Number.isFinite(rawScore) ? rawScore : 0;
  return (
    <div className="match-signal">
      <div className="match-signal-header">
        <Typography.Text strong>{label}</Typography.Text>
        <Tag color={numericScore > 0 ? "green" : "default"}>{numericScore.toFixed(2)}</Tag>
      </div>
      <div className="match-object-row">
        {values.length ? (
          values.map((value) => (
            <Tag key={value} color="gold">
              {value}
            </Tag>
          ))
        ) : (
          <Typography.Text type="secondary">No exact term</Typography.Text>
        )}
      </div>
    </div>
  );
};

const HighlightedText = ({ text, terms }: { text: string; terms: string[] }) => {
  const matchedTerms = uniqueTerms(terms).filter(Boolean);
  if (!matchedTerms.length) {
    return <>{text}</>;
  }
  const pattern = new RegExp(`(${matchedTerms.map(escapeRegExp).join("|")})`, "gi");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, index) =>
        matchedTerms.some((term) => term.toLowerCase() === part.toLowerCase()) ? (
          <mark className="match-highlight" key={`${part}-${index}`}>
            {part}
          </mark>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        ),
      )}
    </>
  );
};

const findMatchedTerms = (terms: string[], text: string) => {
  const normalizedText = text.toLowerCase();
  return uniqueTerms(terms).filter((term) => normalizedText.includes(term.toLowerCase()));
};

const uniqueTerms = (terms: string[]) => Array.from(new Set(terms.map((term) => term.trim()).filter(Boolean)));

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const StatusTag = ({ status }: { status: string }) => {
  const color =
    status === "completed" || status === "selected" || status === "executed"
      ? "green"
      : status === "failed" || status === "error"
        ? "red"
        : status === "running"
          ? "processing"
          : status === "candidate"
            ? "default"
            : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDateTime = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const flattenSections = (sections: PlanSection[]) => {
  const rows = new Map<number, PlanSection>();
  const visit = (items: PlanSection[]) => {
    for (const item of items) {
      rows.set(item.id, item);
      visit(item.children || []);
    }
  };
  visit(sections);
  return rows;
};
