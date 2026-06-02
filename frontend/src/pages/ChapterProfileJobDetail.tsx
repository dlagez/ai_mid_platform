import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeftOutlined, DeleteOutlined, PauseCircleOutlined, PlayCircleOutlined, ReloadOutlined, SearchOutlined, StopOutlined } from "@ant-design/icons";
import { Button, Card, Col, Descriptions, Empty, Form, Input, Modal, Popconfirm, Progress, Row, Select, Space, Table, Tabs, Tag, Tree, Typography, message } from "antd";
import type { TablePaginationConfig } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  cancelChapterProfileJob,
  deleteChapterProfileJob,
  getChapterProfileJobSections,
  getChapterProfileJob,
  listChapterProfileJobItems,
  listChapterProfileJobProfiles,
  pauseChapterProfileJob,
  restartChapterProfileJob,
  resumeChapterProfileJob,
  type ChapterProfileGenerationItem,
  type ChapterProfileGenerationJob,
  type ChapterReviewProfile,
  type DocumentParseResult,
  type PlanSection,
} from "../services/documentService";
import { listReviewTaskCheckpointMatches, type CheckpointMatchWithCheckpoint } from "../services/reviewTaskService";

const { TextArea } = Input;

type ProfileFilterValues = {
  status?: string;
  keyword?: string;
};

type ProfileFormValues = {
  evidence_code?: string | null;
  evidence_text?: string;
  object_terms?: string[];
  document_id?: string;
  section_id?: string;
  chapter_title?: string | null;
  chapter_path?: string | null;
  source_text?: string | null;
  confidence?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
};

export const ChapterProfileJobDetailPage = () => {
  const { id } = useParams();
  const jobId = Number(id);
  const navigate = useNavigate();
  const [job, setJob] = useState<ChapterProfileGenerationJob | null>(null);
  const [items, setItems] = useState<ChapterProfileGenerationItem[]>([]);
  const [profiles, setProfiles] = useState<ChapterReviewProfile[]>([]);
  const [parsed, setParsed] = useState<DocumentParseResult | null>(null);
  const [matches, setMatches] = useState<CheckpointMatchWithCheckpoint[]>([]);
  const [selectedSectionId, setSelectedSectionId] = useState<number | null>(null);
  const [expandedSectionKeys, setExpandedSectionKeys] = useState<string[]>([]);
  const [profileQuery, setProfileQuery] = useState<ProfileFilterValues & { page: number; page_size: number }>({
    page: 1,
    page_size: 20,
  });
  const [editingProfile, setEditingProfile] = useState<ChapterReviewProfile | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [queueActionLoading, setQueueActionLoading] = useState(false);
  const [filterForm] = Form.useForm<ProfileFilterValues>();
  const [profileForm] = Form.useForm<ProfileFormValues>();

  const load = async () => {
    if (!jobId) {
      return;
    }
    setLoading(true);
    try {
      const [jobResult, itemResult, profileResult] = await Promise.all([
        getChapterProfileJob(jobId),
        listChapterProfileJobItems(jobId, { page: 1, page_size: 500 }),
        listChapterProfileJobProfiles(jobId, { page: 1, page_size: 500 }),
      ]);
      const [parseResult, matchResult] = await Promise.all([
        getChapterProfileJobSections(jobResult.id),
        jobResult.task_id ? listReviewTaskCheckpointMatches(jobResult.task_id) : Promise.resolve({ items: [], total: 0 }),
      ]);
      setJob(jobResult);
      setItems(itemResult.items);
      setProfiles(profileResult.items);
      setParsed(parseResult);
      setMatches(matchResult.items);
      setExpandedSectionKeys(getSectionKeys(parseResult.sections));
      setSelectedSectionId((current) => current ?? findFirstProfileSectionId(profileResult.items) ?? findFirstSection(parseResult.sections)?.id ?? null);
    } catch {
      message.error("Failed to load chapter profile job.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [jobId]);

  const filteredProfiles = useMemo(() => filterProfiles(profiles, profileQuery), [profiles, profileQuery]);
  const pagedProfiles = useMemo(
    () =>
      filteredProfiles.slice(
        (profileQuery.page - 1) * profileQuery.page_size,
        profileQuery.page * profileQuery.page_size,
      ),
    [filteredProfiles, profileQuery.page, profileQuery.page_size],
  );
  const percent = job?.total_sections ? Math.round((job.processed_sections / job.total_sections) * 100) : 0;
  const profilesBySectionId = useMemo(() => groupProfilesBySectionId(profiles), [profiles]);
  const itemsBySectionId = useMemo(() => groupItemsBySectionId(items), [items]);
  const matchesBySectionId = useMemo(() => groupMatchesBySectionId(matches), [matches]);
  const selectedSection = useMemo(
    () => (parsed && selectedSectionId ? findSection(parsed.sections, selectedSectionId) : null),
    [parsed, selectedSectionId],
  );
  const selectedProfiles = selectedSection ? profilesBySectionId.get(selectedSection.id) ?? [] : [];
  const selectedItem = selectedSection ? itemsBySectionId.get(selectedSection.id) ?? null : null;
  const selectedMatches = selectedSection ? matchesBySectionId.get(selectedSection.id) ?? [] : [];

  const applyFilter = () => {
    const values = filterForm.getFieldsValue();
    setProfileQuery((current) => ({ ...current, ...values, page: 1 }));
  };

  const handleProfileTableChange = (pagination: TablePaginationConfig) => {
    setProfileQuery((current) => ({
      ...current,
      page: pagination.current ?? 1,
      page_size: pagination.pageSize ?? 20,
    }));
  };

  const openProfile = (profile: ChapterReviewProfile) => {
    setSelectedProfileId(profile.id);
    setEditingProfile(profile);
    profileForm.setFieldsValue(toProfileFormValues(profile));
  };

  const handleRestart = async () => {
    if (!job) {
      return;
    }
    setQueueActionLoading(true);
    try {
      await restartChapterProfileJob(job.id);
      message.success(`Chapter profile job #${job.id} restarted.`);
      await load();
    } catch {
      message.error("Failed to restart chapter profile job.");
    } finally {
      setQueueActionLoading(false);
    }
  };

  const handlePause = async () => {
    if (!job) {
      return;
    }
    setQueueActionLoading(true);
    try {
      await pauseChapterProfileJob(job.id);
      message.success(`Chapter profile job #${job.id} paused.`);
      await load();
    } catch {
      message.error("Failed to pause chapter profile job.");
    } finally {
      setQueueActionLoading(false);
    }
  };

  const handleResume = async () => {
    if (!job) {
      return;
    }
    setQueueActionLoading(true);
    try {
      await resumeChapterProfileJob(job.id);
      message.success(`Chapter profile job #${job.id} continued.`);
      await load();
    } catch {
      message.error("Failed to continue chapter profile job.");
    } finally {
      setQueueActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!job) {
      return;
    }
    setQueueActionLoading(true);
    try {
      await cancelChapterProfileJob(job.id);
      message.success(`Chapter profile job #${job.id} cancelled.`);
      await load();
    } catch {
      message.error("Failed to cancel chapter profile job.");
    } finally {
      setQueueActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!job) {
      return;
    }
    setQueueActionLoading(true);
    try {
      await deleteChapterProfileJob(job.id);
      message.success(`Chapter profile job #${job.id} deleted.`);
      navigate("/construction-plan/profile-jobs");
    } catch {
      message.error("Failed to delete chapter profile job.");
    } finally {
      setQueueActionLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Chapter Profile Job #{jobId}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/construction-plan/profile-jobs")}>
            Back
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            loading={queueActionLoading}
            disabled={!job || !canRestartProfileJob(job)}
            onClick={() => void handleRestart()}
          >
            Restart
          </Button>
          <Button
            icon={<PauseCircleOutlined />}
            loading={queueActionLoading}
            disabled={!job || !canPauseProfileJob(job)}
            onClick={() => void handlePause()}
          >
            Pause
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            loading={queueActionLoading}
            disabled={!job || !canResumeProfileJob(job)}
            onClick={() => void handleResume()}
          >
            Continue
          </Button>
          <Popconfirm
            title="Cancel this chapter profile job?"
            okText="Cancel Job"
            cancelText="Keep"
            disabled={!job || !canCancelProfileJob(job)}
            onConfirm={() => void handleCancel()}
          >
            <Button
              danger
              icon={<StopOutlined />}
              loading={queueActionLoading}
              disabled={!job || !canCancelProfileJob(job)}
            >
              Cancel
            </Button>
          </Popconfirm>
          <Popconfirm
            title={`Delete chapter profile job #${jobId}?`}
            description="This will remove this job and its generated profiles."
            okText="Delete"
            cancelText="Keep"
            disabled={!job || !canDeleteProfileJob(job)}
            onConfirm={() => void handleDelete()}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={queueActionLoading}
              disabled={!job || !canDeleteProfileJob(job)}
            >
              Delete
            </Button>
          </Popconfirm>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
            Reload
          </Button>
        </Space>
      </div>

      <Card>
        {job ? (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Descriptions size="small" column={4}>
              <Descriptions.Item label="Document ID">{job.document_id}</Descriptions.Item>
              <Descriptions.Item label="Status">
                <StatusTag status={job.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Processed">
                {job.processed_sections}/{job.total_sections}
              </Descriptions.Item>
              <Descriptions.Item label="Celery Task">{job.celery_task_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="Created">{job.created_count}</Descriptions.Item>
              <Descriptions.Item label="Updated">{job.updated_count}</Descriptions.Item>
              <Descriptions.Item label="Rule Only">{job.rule_only_count}</Descriptions.Item>
              <Descriptions.Item label="Failed">{job.failed_count}</Descriptions.Item>
              <Descriptions.Item label="Started At">{formatDate(job.started_at)}</Descriptions.Item>
              <Descriptions.Item label="Finished At">{formatDate(job.finished_at)}</Descriptions.Item>
            </Descriptions>
            <Progress percent={percent} status={job.status === "failed" ? "exception" : undefined} />
            {job.error_message ? <Typography.Text type="danger">{job.error_message}</Typography.Text> : null}
          </Space>
        ) : (
          <Typography.Text type="secondary">No job loaded.</Typography.Text>
        )}
      </Card>

      <Card title="Document Section Tree">
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={9}>
            <div className="plan-section-tree chapter-profile-section-tree">
              {parsed?.sections.length ? (
                <Tree
                  blockNode
                  expandedKeys={expandedSectionKeys}
                  onExpand={(keys) => setExpandedSectionKeys(keys.map(String))}
                  selectedKeys={selectedSectionId ? [String(selectedSectionId)] : []}
                  treeData={toSectionTreeData(parsed.sections, profilesBySectionId, itemsBySectionId, matchesBySectionId)}
                  onSelect={(keys) => setSelectedSectionId(keys[0] ? Number(keys[0]) : null)}
                />
              ) : (
                <Empty description="No parsed section tree found." />
              )}
            </div>
          </Col>
          <Col xs={24} lg={15}>
            <div className="plan-section-content chapter-profile-section-detail">
              {selectedSection ? (
                <SectionReviewPanel
                  section={selectedSection}
                  profiles={selectedProfiles}
                  generationItem={selectedItem}
                  matches={selectedMatches}
                />
              ) : (
                <Empty description="Select a section" />
              )}
            </div>
          </Col>
        </Row>
      </Card>

      <Card title="Section Queue Details">
        <Table<ChapterProfileGenerationItem>
          rowKey="id"
          loading={loading}
          dataSource={items}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: "Section ID", dataIndex: "section_id", width: 100 },
            {
              title: "Section",
              dataIndex: "section_title",
              ellipsis: true,
              render: (value: string | null, record) => value || record.section_path || "-",
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 130,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Profile ID",
              dataIndex: "profile_id",
              width: 100,
              render: (value: number | null) => value ?? "-",
            },
            {
              title: "LLM",
              dataIndex: "used_llm",
              width: 90,
              render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? "used" : "no"}</Tag>,
            },
            {
              title: "Confidence",
              dataIndex: "confidence",
              width: 110,
              render: (value: number | null) => (value == null ? "-" : Number(value).toFixed(2)),
            },
            {
              title: "Message",
              dataIndex: "message",
              ellipsis: true,
              render: (value: string | null) => value || "-",
            },
            {
              title: "Finished At",
              dataIndex: "finished_at",
              width: 170,
              render: formatDate,
            },
          ]}
        />
      </Card>
    </div>
  );
};

const SectionReviewPanel = ({
  section,
  profiles,
  generationItem,
  matches,
}: {
  section: PlanSection;
  profiles: ChapterReviewProfile[];
  generationItem: ChapterProfileGenerationItem | null;
  matches: CheckpointMatchWithCheckpoint[];
}) => (
  <Space direction="vertical" size={16} style={{ width: "100%" }}>
    <div>
      <Space size={8} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {section.title}
        </Typography.Title>
        {section.section_no ? <Tag>{section.section_no}</Tag> : null}
        <Tag>section #{section.id}</Tag>
        {generationItem ? <StatusTag status={generationItem.status} /> : null}
      </Space>
      <Typography.Text type="secondary">
        level {section.level} / parse result {section.parse_result_id}
      </Typography.Text>
    </div>
    <Tabs
      items={[
        {
          key: "section",
          label: "Section",
          children: (
            <Typography.Paragraph className="chapter-profile-text-block">
              {section.content || "No content found for this section."}
            </Typography.Paragraph>
          ),
        },
        {
          key: "profile",
          label: `Profile (${profiles.length})`,
          children: profiles.length ? (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              {profiles.map((profile) => (
                <ProfileSummary key={profile.id} profile={profile} />
              ))}
            </Space>
          ) : (
            <Empty description="No profile generated for this section." />
          ),
        },
        {
          key: "checkpoints",
          label: `Checkpoints (${matches.length})`,
          children: matches.length ? <CheckpointMatchTable matches={matches} /> : <Empty description="No checkpoint matches for this section." />,
        },
      ]}
    />
  </Space>
);

const ProfileSummary = ({ profile }: { profile: ChapterReviewProfile }) => (
  <Card size="small" title={profile.evidence_code || `PROFILE-${profile.id}`} className="chapter-profile-detail-card">
    <Descriptions size="small" column={2}>
      <Descriptions.Item label="Evidence" span={2}>{profile.evidence_text || "-"}</Descriptions.Item>
      <Descriptions.Item label="Confidence">
        <ConfidenceTag confidence={profile.confidence} />
      </Descriptions.Item>
      <Descriptions.Item label="Objects" span={2}>
        <TagList values={profile.object_terms} />
      </Descriptions.Item>
      <Descriptions.Item label="Source" span={2}>
        {profile.source_text || "-"}
      </Descriptions.Item>
    </Descriptions>
  </Card>
);

const CheckpointMatchTable = ({ matches }: { matches: CheckpointMatchWithCheckpoint[] }) => (
  <Table<CheckpointMatchWithCheckpoint>
    rowKey="id"
    size="small"
    dataSource={matches}
    pagination={{ pageSize: 8 }}
    columns={[
      {
        title: "Rule",
        render: (_, record) => record.checkpoint?.rule_text || `Checkpoint #${record.checkpoint_id}`,
        ellipsis: true,
      },
      {
        title: "Score",
        dataIndex: "match_score",
        width: 90,
        render: (value: number) => Number(value).toFixed(2),
      },
      {
        title: "Status",
        dataIndex: "status",
        width: 110,
        render: (value: string) => <StatusTag status={value} />,
      },
      {
        title: "Reason",
        dataIndex: "match_reason",
        ellipsis: true,
        render: (value: string | null) => value || "-",
      },
    ]}
    expandable={{
      expandedRowRender: (record) => (
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="Objects">
            <TagList values={record.checkpoint?.object_terms ?? []} />
          </Descriptions.Item>
          <Descriptions.Item label="Clause">{record.checkpoint?.clause_text || "-"}</Descriptions.Item>
        </Descriptions>
      ),
    }}
  />
);

const ProfileForm = ({
  form,
}: {
  form: ReturnType<typeof Form.useForm<ProfileFormValues>>[0];
}) => (
  <Form form={form} layout="vertical" disabled requiredMark={false}>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="evidence_code" label="证据编码" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="document_id" label="施工方案文档ID" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="section_id" label="施工方案章节ID" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
    </Space>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="chapter_title" label="章节标题" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="confidence" label="画像置信度" style={{ width: 150 }}>
        <Input />
      </Form.Item>
    </Space>
    <Form.Item name="chapter_path" label="章节路径">
      <Input />
    </Form.Item>
    <Form.Item name="evidence_text" label="方案证据点">
      <TextArea rows={3} />
    </Form.Item>
    <Form.Item name="object_terms" label="对象词">
      <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
    </Form.Item>
    <Form.Item name="source_text" label="原文片段">
      <TextArea rows={4} />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="created_at" label="创建时间" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="updated_at" label="更新时间" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
    </Space>
  </Form>
);

const formatJson = (value: unknown) => JSON.stringify(value ?? [], null, 2);

const toSectionTreeData = (
  sections: PlanSection[],
  profilesBySectionId: Map<number, ChapterReviewProfile[]>,
  itemsBySectionId: Map<number, ChapterProfileGenerationItem>,
  matchesBySectionId: Map<number, CheckpointMatchWithCheckpoint[]>,
): DataNode[] =>
  sections.map((section) => {
    const profileCount = profilesBySectionId.get(section.id)?.length ?? 0;
    const matchCount = matchesBySectionId.get(section.id)?.length ?? 0;
    const generationItem = itemsBySectionId.get(section.id);
    return {
      key: String(section.id),
      title: (
        <Space size={6} wrap>
          <span>{section.title}</span>
          {profileCount ? <Tag color="green">P {profileCount}</Tag> : null}
          {matchCount ? <Tag color="blue">C {matchCount}</Tag> : null}
          {generationItem && generationItem.status !== "success" ? <StatusTag status={generationItem.status} /> : null}
        </Space>
      ),
      children: toSectionTreeData(section.children, profilesBySectionId, itemsBySectionId, matchesBySectionId),
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

const findFirstProfileSectionId = (profiles: ChapterReviewProfile[]) => profiles[0]?.section_id ?? null;

const groupProfilesBySectionId = (profiles: ChapterReviewProfile[]) => {
  const grouped = new Map<number, ChapterReviewProfile[]>();
  for (const profile of profiles) {
    grouped.set(profile.section_id, [...(grouped.get(profile.section_id) ?? []), profile]);
  }
  return grouped;
};

const groupItemsBySectionId = (items: ChapterProfileGenerationItem[]) => {
  const grouped = new Map<number, ChapterProfileGenerationItem>();
  for (const item of items) {
    if (item.section_id != null) {
      grouped.set(item.section_id, item);
    }
  }
  return grouped;
};

const groupMatchesBySectionId = (matches: CheckpointMatchWithCheckpoint[]) => {
  const grouped = new Map<number, CheckpointMatchWithCheckpoint[]>();
  for (const match of matches) {
    grouped.set(match.section_id, [...(grouped.get(match.section_id) ?? []), match]);
  }
  return grouped;
};

const profileStatusOptions = [
  { value: "high", label: "high" },
  { value: "medium", label: "medium" },
  { value: "low", label: "low" },
];

const getProfileStatus = (profile: ChapterReviewProfile) => {
  const confidence = Number(profile.confidence ?? 0);
  if (confidence >= 0.7) {
    return "high";
  }
  if (confidence >= 0.4) {
    return "medium";
  }
  return "low";
};

const filterProfiles = (profiles: ChapterReviewProfile[], query: ProfileFilterValues) => {
  const keyword = normalizeText(query.keyword);
  return profiles.filter((profile) => {
    if (query.status && getProfileStatus(profile) !== query.status) {
      return false;
    }
    if (keyword) {
      const haystack = normalizeText(
        [
          profile.evidence_code,
          profile.evidence_text,
          profile.object_terms.join(" "),
          profile.chapter_title,
          profile.chapter_path,
          profile.source_text,
        ].join(" "),
      );
      if (!haystack.includes(keyword)) {
        return false;
      }
    }
    return true;
  });
};

const toProfileFormValues = (profile: ChapterReviewProfile): ProfileFormValues => ({
  evidence_code: profile.evidence_code,
  evidence_text: profile.evidence_text,
  object_terms: profile.object_terms,
  document_id: String(profile.document_id),
  section_id: String(profile.section_id),
  chapter_title: profile.chapter_title || "",
  chapter_path: profile.chapter_path || "",
  source_text: profile.source_text,
  confidence: profile.confidence == null ? "" : Number(profile.confidence).toFixed(2),
  status: profile.status,
  created_at: formatDate(profile.created_at),
  updated_at: formatDate(profile.updated_at),
});

const normalizeText = (value: unknown) => String(value ?? "").trim().toLowerCase();

const unique = (values: string[]) => {
  const seen = new Set<string>();
  return values.filter((value) => {
    const text = value.trim();
    if (!text || seen.has(text)) {
      return false;
    }
    seen.add(text);
    return true;
  });
};

const StatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success"
      ? "green"
      : status === "selected" || status === "active"
      ? "green"
      : status === "partial_success" || status === "rule_only" || status === "paused"
        ? "gold"
        : status === "failed" || status === "cancelled"
          ? "red"
          : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const RiskTag = ({ risk }: { risk?: string | null }) => {
  const color = risk === "critical" ? "red" : risk === "major" ? "orange" : risk === "minor" ? "blue" : "default";
  return <Tag color={color}>{risk || "-"}</Tag>;
};

const canRestartProfileJob = (job: ChapterProfileGenerationJob) =>
  ["queued", "running", "failed", "partial_success"].includes(job.status) &&
  (job.processed_sections < job.total_sections || job.failed_count > 0);

const canPauseProfileJob = (job: ChapterProfileGenerationJob) => ["queued", "running"].includes(job.status);

const canResumeProfileJob = (job: ChapterProfileGenerationJob) => job.status === "paused";

const canCancelProfileJob = (job: ChapterProfileGenerationJob) => ["queued", "running", "paused"].includes(job.status);

const canDeleteProfileJob = (job: ChapterProfileGenerationJob) =>
  ["success", "partial_success", "failed", "cancelled"].includes(job.status);

const formatDate = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const TagList = ({ values }: { values?: string[] }) => (
  <Space size={4} wrap>
    {(values || []).slice(0, 4).map((value) => (
      <Tag key={value}>{value}</Tag>
    ))}
    {(values || []).length > 4 ? <Typography.Text type="secondary">+{(values || []).length - 4}</Typography.Text> : null}
    {!(values || []).length ? <Typography.Text type="secondary">-</Typography.Text> : null}
  </Space>
);

const ConfidenceTag = ({ confidence }: { confidence: number | null }) => {
  if (confidence == null) {
    return <Tag>-</Tag>;
  }
  const value = Number(confidence);
  const color = value >= 0.7 ? "green" : value >= 0.4 ? "gold" : "default";
  return <Tag color={color}>{value.toFixed(2)}</Tag>;
};
