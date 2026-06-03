import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  NodeIndexOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Descriptions, Empty, Row, Space, Table, Tag, Tree, Typography, message } from "antd";
import type { DataNode } from "antd/es/tree";
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
import {
  getChapterProfileJobSections,
  getDocumentSections,
  listChapterProfileJobs,
  type PlanSection,
} from "../services/documentService";

export const ReviewTaskDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const taskId = Number(id);
  const [task, setTask] = useState<ReviewTask | null>(null);
  const [matches, setMatches] = useState<CheckpointMatchWithCheckpoint[]>([]);
  const [sections, setSections] = useState<PlanSection[]>([]);
  const [selectedSection, setSelectedSection] = useState<PlanSection | null>(null);
  const [expandedSectionKeys, setExpandedSectionKeys] = useState<string[]>([]);
  const [sectionById, setSectionById] = useState<Map<number, PlanSection>>(new Map());
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<CheckpointMatchListQuery>({ matched_only: true });
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
      return [];
    }
    setLoading((current) => ({ ...current, matches: true }));
    try {
      const result = await listReviewTaskCheckpointMatches(taskId, nextQuery);
      setMatches(result.items);
      setTotal(result.total);
      setQuery(nextQuery);
      return result.items;
    } catch {
      message.error("Failed to load checkpoint matches.");
      return [];
    } finally {
      setLoading((current) => ({ ...current, matches: false }));
    }
  };

  const loadSections = async (task: ReviewTask, preferredSectionIds: number[] = []) => {
    setLoading((current) => ({ ...current, sections: true }));
    try {
      const profileJobs = await listChapterProfileJobs({
        document_id: task.plan_document_id,
        page: 1,
        page_size: 100,
      });
      const profileJob = profileJobs.items.find((job) => job.task_id === task.id) ?? profileJobs.items[0];
      const result = profileJob
        ? await getChapterProfileJobSections(profileJob.id)
        : await getDocumentSections(task.plan_document_id);
      setSections(result.sections);
      setExpandedSectionKeys(getSectionKeys(result.sections));
      setSelectedSection(findFirstExistingSection(result.sections, preferredSectionIds) ?? findFirstSection(result.sections));
      setSectionById(flattenSections(result.sections));
    } catch {
      setSections([]);
      setSelectedSection(null);
      setExpandedSectionKeys([]);
      setSectionById(new Map());
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
    const nextMatches = await loadMatches();
    await loadSections(nextTask, nextMatches.map((match) => match.section_id));
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
      await refresh();
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
      await loadMatches(query);
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

  const matchesBySectionId = groupMatchesBySectionId(matches);
  const unmappedMatches = getUnmappedMatches(matches, sectionById);

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
        title="Review Tree"
        extra={
          <Space>
            <Typography.Text type="secondary">{total} matches</Typography.Text>
            <Button
              size="small"
              type={query.matched_only ? "primary" : "default"}
              onClick={() => void loadMatches({ matched_only: true, status: undefined })}
            >
              Matched
            </Button>
            <Button
              size="small"
              type={!query.matched_only && !query.status ? "primary" : "default"}
              onClick={() => void loadMatches({ matched_only: false, status: undefined })}
            >
              All
            </Button>
          </Space>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={9}>
            <div className="plan-section-tree review-task-section-tree">
              {sections.length ? (
                <Tree
                  blockNode
                  expandedKeys={expandedSectionKeys}
                  onExpand={(keys) => setExpandedSectionKeys(keys.map(String))}
                  selectedKeys={selectedSection ? [String(selectedSection.id)] : []}
                  treeData={toSectionTreeData(sections, matchesBySectionId)}
                  onSelect={(keys) => setSelectedSection(keys[0] ? findSection(sections, Number(keys[0])) : null)}
                />
              ) : (
                <Empty description={loading.sections ? "Loading sections..." : "No plan sections found."} />
              )}
            </div>
          </Col>
          <Col xs={24} lg={15}>
            <div className="plan-section-content review-task-section-detail">
              {selectedSection ? (
                <SectionMatchDetail
                  section={selectedSection}
                  matches={matchesBySectionId.get(selectedSection.id) ?? []}
                  sectionById={sectionById}
                  loading={loading.matches || loading.sections}
                />
              ) : (
                <Empty description="Select a section" />
              )}
            </div>
          </Col>
        </Row>
        {unmappedMatches.length ? (
          <div className="review-task-unmapped-matches">
            <Typography.Title level={5}>Unmapped Matches</Typography.Title>
            <Typography.Text type="secondary">
              These matches reference section IDs that are not present in the loaded section tree.
            </Typography.Text>
            <CheckpointMatchTable
              matches={unmappedMatches}
              sectionById={sectionById}
              loading={loading.matches || loading.sections}
              pageSize={8}
            />
          </div>
        ) : null}
      </Card>
    </div>
  );
};

const SectionMatchDetail = ({
  section,
  matches,
  sectionById,
  loading,
}: {
  section: PlanSection;
  matches: CheckpointMatchWithCheckpoint[];
  sectionById: Map<number, PlanSection>;
  loading: boolean;
}) => (
  <Space direction="vertical" size={16} style={{ width: "100%" }}>
    <div>
      <Space wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {section.title}
        </Typography.Title>
        <Tag>Level {section.level}</Tag>
        {section.section_no ? <Tag color="blue">{section.section_no}</Tag> : null}
        <Tag color={matches.length ? "green" : "default"}>{matches.length} matches</Tag>
      </Space>
      <Typography.Paragraph className="review-task-section-content">
        {section.content || "No content found for this section."}
      </Typography.Paragraph>
    </div>

    {matches.length ? (
      <CheckpointMatchTable matches={matches} sectionById={sectionById} loading={loading} pageSize={8} />
    ) : (
      <Empty description="No checkpoint matches under this section." />
    )}
  </Space>
);

const CheckpointMatchTable = ({
  matches,
  sectionById,
  loading,
  pageSize,
}: {
  matches: CheckpointMatchWithCheckpoint[];
  sectionById: Map<number, PlanSection>;
  loading: boolean;
  pageSize: number;
}) => (
  <Table<CheckpointMatchWithCheckpoint>
    rowKey="id"
    size="small"
    loading={loading}
    dataSource={matches}
    expandable={{
      expandedRowRender: (record) => (
        <MatchDetailPanel record={record} section={sectionById.get(record.section_id) ?? null} />
      ),
      rowExpandable: () => true,
    }}
    pagination={{ pageSize, showSizeChanger: false }}
    columns={[
      {
        title: "Section",
        dataIndex: "section",
        width: 180,
        render: (_, record) => {
          const matchedSection = sectionById.get(record.section_id) ?? null;
          return (
            <Space direction="vertical" size={0}>
              <Typography.Text strong>
                {matchedSection?.title ?? record.section?.title ?? `Section ${record.section_id}`}
              </Typography.Text>
              <Typography.Text type="secondary">{matchedSection?.section_no ?? record.section?.section_no ?? "-"}</Typography.Text>
            </Space>
          );
        },
      },
      {
        title: "Checkpoint",
        dataIndex: "checkpoint",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text ellipsis style={{ maxWidth: 440 }}>
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
        width: 90,
        render: (value: number) => value.toFixed(2),
      },
      {
        title: "Status",
        dataIndex: "status",
        width: 110,
        render: (value: string) => <StatusTag status={value} />,
      },
      { title: "Reason", dataIndex: "match_reason", width: 180, ellipsis: true },
    ]}
  />
);

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
  const profileObjects = stringValues(record.profile?.object_terms ?? []);
  const profileContext = stringValues([record.profile?.chapter_title, record.profile?.chapter_path]);
  const profileSemanticText = [
    record.profile?.chapter_title,
    record.profile?.chapter_path,
    ...(record.profile?.object_terms ?? []),
    record.profile?.evidence_text,
  ].filter(Boolean).join("\n");
  const checkpointObjects = record.checkpoint?.object_terms ?? [];
  const checkpointContext = stringValues([record.checkpoint?.rule_text]);
  const checkpointSemanticText = [
    record.checkpoint?.rule_text,
    ...(record.checkpoint?.object_terms ?? []),
  ].filter(Boolean).join("\n");
  const checkpointText = [record.checkpoint?.rule_text, record.checkpoint?.clause_text].filter(Boolean).join("\n\n");
  const objectPairs = findMatchedPairs(profileObjects, checkpointObjects);
  const contextPairs = findMatchedPairs(profileContext, checkpointContext);
  const matchedObjectTerms = objectPairs.flatMap((pair) => [pair.left, pair.right]);
  const matchedContextTerms = contextPairs.flatMap((pair) => [pair.left, pair.right]);
  const highlightTerms = [...matchedObjectTerms, ...matchedContextTerms];

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
              <Tag key={term} color={matchedObjectTerms.includes(term) ? "gold" : "default"}>
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
        <MatchSignal
          label="Objects"
          score={record.match_dimensions?.object_match}
          pairs={objectPairs}
          comparedLeft={profileObjects}
          comparedRight={checkpointObjects}
        />
        <MatchSignal
          label="Context"
          score={record.match_dimensions?.context_match}
          pairs={contextPairs}
          comparedLeft={profileContext}
          comparedRight={checkpointContext}
        />
        <MatchSignal
          label="Semantic Text"
          score={record.match_dimensions?.semantic_similarity}
          pairs={[]}
          comparedLeft={stringValues([profileSemanticText])}
          comparedRight={stringValues([checkpointSemanticText])}
        />
        {record.match_reason ? <div className="match-reason">{record.match_reason}</div> : null}
      </div>
    </div>
  );
};

const MatchSignal = ({
  label,
  score,
  pairs,
  comparedLeft,
  comparedRight,
}: {
  label: string;
  score: unknown;
  pairs: MatchPair[];
  comparedLeft: string[];
  comparedRight: string[];
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
        {pairs.length ? (
          pairs.map((pair) => (
            <Tag key={`${pair.left}-${pair.right}`} color="gold">
              {pair.left} &lt;-&gt; {pair.right}
            </Tag>
          ))
        ) : (
          <Typography.Text type="secondary">{numericScore > 0 ? "Score matched without exact term pair" : "No match"}</Typography.Text>
        )}
      </div>
      <div className="match-compared">
        <Typography.Text type="secondary">Section/Profile</Typography.Text>
        <ComparedValues values={comparedLeft} />
        <Typography.Text type="secondary">Checkpoint</Typography.Text>
        <ComparedValues values={comparedRight} />
      </div>
    </div>
  );
};

const ComparedValues = ({ values }: { values: string[] }) =>
  values.length ? (
    <div className="match-compared-values">{values.map((value) => <span key={value}>{value}</span>)}</div>
  ) : (
    <Typography.Text type="secondary">-</Typography.Text>
  );

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

type MatchPair = {
  left: string;
  right: string;
};

const findMatchedPairs = (leftTerms: string[], rightTerms: string[]) => {
  const pairs: MatchPair[] = [];
  for (const left of uniqueTerms(leftTerms)) {
    for (const right of uniqueTerms(rightTerms)) {
      if (termMatches(left, right)) {
        pairs.push({ left, right });
      }
    }
  }
  return pairs;
};

const termMatches = (left: string, right: string) => {
  const normalizedLeft = normalizeMatchText(left);
  const normalizedRight = normalizeMatchText(right);
  if (!normalizedLeft || !normalizedRight) {
    return false;
  }
  if (normalizedLeft.includes(normalizedRight) || normalizedRight.includes(normalizedLeft)) {
    return true;
  }
  const leftTokens = bigrams(normalizedLeft);
  const rightTokens = bigrams(normalizedRight);
  if (!leftTokens.size || !rightTokens.size) {
    return false;
  }
  const intersectionSize = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  return intersectionSize / Math.max(Math.min(leftTokens.size, rightTokens.size), 1) >= 0.6;
};

const bigrams = (value: string) => {
  const tokens = new Set<string>();
  for (let index = 0; index < value.length - 1; index += 1) {
    tokens.add(value.slice(index, index + 2));
  }
  return tokens;
};

const stringValues = (values: unknown[]) =>
  values.map((value) => (value == null ? "" : String(value).trim())).filter(Boolean);

const uniqueTerms = (terms: string[]) => Array.from(new Set(terms.map((term) => term.trim()).filter(Boolean)));

const normalizeMatchText = (value: string) => value.toLowerCase().replace(/\s+/g, "");

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

const groupMatchesBySectionId = (matches: CheckpointMatchWithCheckpoint[]) => {
  const grouped = new Map<number, CheckpointMatchWithCheckpoint[]>();
  for (const match of matches) {
    const rows = grouped.get(match.section_id) ?? [];
    rows.push(match);
    grouped.set(match.section_id, rows);
  }
  return grouped;
};

const getUnmappedMatches = (
  matches: CheckpointMatchWithCheckpoint[],
  sectionById: Map<number, PlanSection>,
) => matches.filter((match) => !sectionById.has(match.section_id));

const toSectionTreeData = (
  sections: PlanSection[],
  matchesBySectionId: Map<number, CheckpointMatchWithCheckpoint[]>,
): DataNode[] =>
  sections.map((section) => {
    const matchCount = matchesBySectionId.get(section.id)?.length ?? 0;
    return {
      key: String(section.id),
      title: (
        <Space size={6} wrap>
          <span>{section.title}</span>
          {matchCount ? <Tag color="blue">C {matchCount}</Tag> : null}
        </Space>
      ),
      children: toSectionTreeData(section.children, matchesBySectionId),
    };
  });

const getSectionKeys = (sections: PlanSection[]): string[] =>
  sections.flatMap((section) => [String(section.id), ...getSectionKeys(section.children)]);

const findSection = (sections: PlanSection[], id: number): PlanSection | null => {
  for (const section of sections) {
    if (section.id === id) {
      return section;
    }
    const child = findSection(section.children, id);
    if (child) {
      return child;
    }
  }
  return null;
};

const findFirstSection = (sections: PlanSection[]): PlanSection | null => {
  const [first] = sections;
  return first ?? null;
};

const findFirstExistingSection = (sections: PlanSection[], sectionIds: number[]): PlanSection | null => {
  for (const sectionId of sectionIds) {
    const section = findSection(sections, sectionId);
    if (section) {
      return section;
    }
  }
  return null;
};

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
