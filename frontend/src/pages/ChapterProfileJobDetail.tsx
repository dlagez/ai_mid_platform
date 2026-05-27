import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeftOutlined, PauseCircleOutlined, PlayCircleOutlined, ReloadOutlined, SearchOutlined, StopOutlined } from "@ant-design/icons";
import { Button, Card, Col, Descriptions, Empty, Form, Input, Modal, Popconfirm, Progress, Row, Select, Space, Table, Tabs, Tag, Tree, Typography, message } from "antd";
import type { TablePaginationConfig } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  cancelChapterProfileJob,
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
  checkpoint_type?: string;
  domain?: string;
  work_type?: string;
  keyword?: string;
};

type ProfileFormValues = {
  profile_code?: string;
  document_id?: string;
  section_id?: string;
  chapter_title?: string | null;
  chapter_path?: string | null;
  chapter_type?: string | null;
  main_domain?: string | null;
  subdomains?: string[];
  construction_objects?: string;
  materials?: string[];
  mentioned_parameters?: string;
  mentioned_methods?: string[];
  mentioned_risks?: string[];
  mentioned_standards?: string[];
  expected_missing_objects?: string[];
  summary?: string | null;
  confidence?: string;
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
                  defaultExpandAll
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
  <Card size="small" title={`PROFILE-${profile.id}`} className="chapter-profile-detail-card">
    <Descriptions size="small" column={2}>
      <Descriptions.Item label="Chapter Type">{profile.chapter_type || "-"}</Descriptions.Item>
      <Descriptions.Item label="Confidence">
        <ConfidenceTag confidence={profile.confidence} />
      </Descriptions.Item>
      <Descriptions.Item label="Domain">{profile.main_domain || "-"}</Descriptions.Item>
      <Descriptions.Item label="Subdomains">
        <TagList values={profile.subdomains} />
      </Descriptions.Item>
      <Descriptions.Item label="Objects" span={2}>
        <TagList values={getConstructionObjectTags(profile)} />
      </Descriptions.Item>
      <Descriptions.Item label="Materials" span={2}>
        <TagList values={profile.materials} />
      </Descriptions.Item>
      <Descriptions.Item label="Parameters" span={2}>
        <TagList values={getParameterTags(profile)} />
      </Descriptions.Item>
      <Descriptions.Item label="Methods" span={2}>
        <TagList values={profile.mentioned_methods} />
      </Descriptions.Item>
      <Descriptions.Item label="Risks" span={2}>
        <TagList values={profile.mentioned_risks} />
      </Descriptions.Item>
      <Descriptions.Item label="Standards" span={2}>
        <TagList values={profile.mentioned_standards} />
      </Descriptions.Item>
      <Descriptions.Item label="Expected Missing" span={2}>
        <TagList values={profile.expected_missing_objects} />
      </Descriptions.Item>
      <Descriptions.Item label="Summary" span={2}>
        {profile.summary || "-"}
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
        title: "Checkpoint",
        render: (_, record) => record.checkpoint?.checkpoint_name || `Checkpoint #${record.checkpoint_id}`,
        ellipsis: true,
      },
      {
        title: "Type",
        width: 180,
        render: (_, record) => record.checkpoint?.checkpoint_type || "-",
      },
      {
        title: "Risk",
        width: 110,
        render: (_, record) => <RiskTag risk={record.checkpoint?.risk_level} />,
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
          <Descriptions.Item label="Targets">
            <TagList values={record.checkpoint?.target_objects ?? []} />
          </Descriptions.Item>
          <Descriptions.Item label="Parameters">
            <TagList values={record.checkpoint?.target_parameters ?? []} />
          </Descriptions.Item>
          <Descriptions.Item label="Goal">{record.checkpoint?.check_goal || "-"}</Descriptions.Item>
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
      <Form.Item name="profile_code" label="章节画像主键" style={{ flex: 1 }}>
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
      <Form.Item name="chapter_type" label="章节类型" style={{ flex: 1 }}>
        <Select options={chapterTypeOptions} />
      </Form.Item>
      <Form.Item name="confidence" label="画像置信度" style={{ width: 150 }}>
        <Input />
      </Form.Item>
    </Space>
    <Form.Item name="chapter_path" label="章节路径">
      <Input />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="main_domain" label="主专业领域" style={{ flex: 1 }}>
        <Input />
      </Form.Item>
      <Form.Item name="subdomains" label="子领域列表" style={{ flex: 2 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
    </Space>
    <Form.Item name="construction_objects" label="识别到的施工对象列表">
      <TextArea rows={5} />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="materials" label="识别到的材料列表" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
      <Form.Item name="mentioned_methods" label="识别到的施工方法列表" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
    </Space>
    <Form.Item name="mentioned_parameters" label="识别到的参数列表">
      <TextArea rows={5} />
    </Form.Item>
    <Space align="start" style={{ width: "100%" }} className="form-space-row">
      <Form.Item name="mentioned_risks" label="识别到的风险点列表" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
      <Form.Item name="mentioned_standards" label="章节提到的规范标准列表" style={{ flex: 1 }}>
        <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
      </Form.Item>
    </Space>
    <Form.Item name="expected_missing_objects" label="按章节类型推断应出现但未出现的对象">
      <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
    </Form.Item>
    <Form.Item name="summary" label="章节审查画像摘要">
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

const formatParameter = (value: ChapterReviewProfile["mentioned_parameters"][number]) => {
  if (typeof value === "string") {
    return value;
  }
  const name = String(value.name ?? "").trim();
  const rawValue = String(value.value ?? "").trim();
  const unit = String(value.unit ?? "").trim();
  const sourceText = String(value.source_text ?? "").trim();
  const parameter = [name, rawValue ? `${rawValue}${unit}` : ""].filter(Boolean).join("：");
  return [parameter, sourceText ? `(${sourceText})` : ""].filter(Boolean).join(" ");
};

const getParameterTags = (profile: ChapterReviewProfile) =>
  (profile.mentioned_parameters || []).map(formatParameter).filter(Boolean);

const getConstructionObjectTags = (profile: ChapterReviewProfile) => {
  const values: string[] = [];
  for (const item of profile.construction_objects || []) {
    const name = typeof item.object_name === "string" ? item.object_name : "";
    if (name) {
      values.push(name);
    }
    const matchedTerms = Array.isArray(item.matched_terms) ? item.matched_terms : [];
    for (const term of matchedTerms) {
      if (typeof term === "string") {
        values.push(term);
      }
    }
  }
  return unique(values);
};

const getScenarioTerms = (profile: ChapterReviewProfile) =>
  unique([...(profile.mentioned_methods || []), ...(profile.mentioned_risks || []), ...(profile.subdomains || [])]);

const chapterTypeOptions = [
  { value: "project_overview", label: "project_overview" },
  { value: "basis", label: "basis" },
  { value: "construction_plan", label: "construction_plan" },
  { value: "construction_process", label: "construction_process" },
  { value: "technical_parameters", label: "technical_parameters" },
  { value: "quality_control", label: "quality_control" },
  { value: "safety_measure", label: "safety_measure" },
  { value: "emergency_plan", label: "emergency_plan" },
  { value: "calculation", label: "calculation" },
  { value: "acceptance", label: "acceptance" },
  { value: "organization", label: "organization" },
  { value: "other", label: "other" },
  { value: "construction_deployment", label: "construction_deployment (legacy)" },
  { value: "construction_technology", label: "construction_technology (legacy)" },
  { value: "safety_control", label: "safety_control (legacy)" },
  { value: "emergency", label: "emergency (legacy)" },
];

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
    if (query.checkpoint_type && profile.chapter_type !== query.checkpoint_type) {
      return false;
    }
    if (query.domain && !normalizeText(profile.main_domain).includes(normalizeText(query.domain))) {
      return false;
    }
    if (query.work_type && !normalizeText(profile.subdomains.join(" ")).includes(normalizeText(query.work_type))) {
      return false;
    }
    if (keyword) {
      const haystack = normalizeText(
        [
          profile.chapter_title,
          profile.chapter_path,
          profile.summary,
          profile.main_domain,
          profile.subdomains.join(" "),
          getConstructionObjectTags(profile).join(" "),
          getParameterTags(profile).join(" "),
          getScenarioTerms(profile).join(" "),
          profile.expected_missing_objects.join(" "),
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
  profile_code: `PROFILE-${profile.id}`,
  document_id: String(profile.document_id),
  section_id: String(profile.section_id),
  chapter_title: profile.chapter_title || "",
  chapter_path: profile.chapter_path || "",
  chapter_type: profile.chapter_type,
  main_domain: profile.main_domain,
  subdomains: profile.subdomains,
  construction_objects: formatJson(profile.construction_objects),
  materials: profile.materials,
  mentioned_parameters: formatJson(profile.mentioned_parameters),
  mentioned_methods: profile.mentioned_methods,
  mentioned_risks: profile.mentioned_risks,
  mentioned_standards: profile.mentioned_standards,
  expected_missing_objects: profile.expected_missing_objects,
  summary: profile.summary,
  confidence: profile.confidence == null ? "" : Number(profile.confidence).toFixed(2),
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
