import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeftOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Form, Input, Modal, Progress, Select, Space, Table, Tag, Typography, message } from "antd";
import type { TablePaginationConfig } from "antd";
import {
  getChapterProfileJob,
  listChapterProfileJobItems,
  listChapterProfileJobProfiles,
  type ChapterProfileGenerationItem,
  type ChapterProfileGenerationJob,
  type ChapterReviewProfile,
} from "../services/documentService";

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
  const [profileQuery, setProfileQuery] = useState<ProfileFilterValues & { page: number; page_size: number }>({
    page: 1,
    page_size: 20,
  });
  const [editingProfile, setEditingProfile] = useState<ChapterReviewProfile | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
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
      setJob(jobResult);
      setItems(itemResult.items);
      setProfiles(profileResult.items);
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

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Chapter Profile Job #{jobId}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/construction-plan/profile-jobs")}>
            Back
          </Button>
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

      <Card title="Generated Profiles">
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 150 }} options={profileStatusOptions} />
          </Form.Item>
          <Form.Item name="checkpoint_type" label="Type">
            <Select allowClear style={{ width: 210 }} options={chapterTypeOptions} />
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
            <Button type="primary" icon={<SearchOutlined />} onClick={applyFilter}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <Table<ChapterReviewProfile>
          rowKey="id"
          loading={loading}
          dataSource={pagedProfiles}
          onRow={(record) => ({
            onClick: () => openProfile(record),
            className: `document-row${selectedProfileId === record.id ? " document-row-selected" : ""}`,
          })}
          pagination={{
            current: profileQuery.page,
            pageSize: profileQuery.page_size,
            total: filteredProfiles.length,
            showSizeChanger: true,
          }}
          onChange={handleProfileTableChange}
          columns={[
            { title: "Code", dataIndex: "id", width: 140, ellipsis: true, render: (value: number) => `PROFILE-${value}` },
            {
              title: "Checkpoint",
              dataIndex: "chapter_title",
              ellipsis: true,
              render: (value: string | null, record) => value || record.chapter_path || "-",
            },
            {
              title: "Type",
              dataIndex: "chapter_type",
              width: 190,
              render: (value: string | null) => value || "-",
            },
            {
              title: "Domain",
              dataIndex: "main_domain",
              width: 130,
              render: (value: string | null) => value || "-",
            },
            {
              title: "Work Type",
              dataIndex: "subdomains",
              width: 160,
              render: (values: string[]) => <TagList values={values} />,
            },
            {
              title: "Targets",
              width: 220,
              render: (_, record) => <TagList values={getConstructionObjectTags(record)} />,
            },
            {
              title: "Parameters",
              width: 200,
              render: (_, record) => <TagList values={getParameterTags(record)} />,
            },
            {
              title: "Keywords",
              width: 220,
              render: (_, record) => <TagList values={getScenarioTerms(record)} />,
            },
            {
              title: "Status",
              width: 120,
              render: (_, record) => <ConfidenceTag confidence={record.confidence} />,
            },
          ]}
        />
      </Card>

      <Modal
        title="章节画像详情"
        open={Boolean(editingProfile)}
        width={920}
        footer={
          <Space>
            <Button onClick={() => setEditingProfile(null)}>Close</Button>
          </Space>
        }
        onCancel={() => setEditingProfile(null)}
      >
        <ProfileForm form={profileForm} />
      </Modal>

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
  { value: "construction_deployment", label: "construction_deployment" },
  { value: "construction_plan", label: "construction_plan" },
  { value: "construction_technology", label: "construction_technology" },
  { value: "construction_process", label: "construction_process" },
  { value: "quality_control", label: "quality_control" },
  { value: "safety_control", label: "safety_control" },
  { value: "emergency", label: "emergency" },
  { value: "calculation", label: "calculation" },
  { value: "other", label: "other" },
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
    status === "success" ? "green" : status === "partial_success" || status === "rule_only" ? "gold" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

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
