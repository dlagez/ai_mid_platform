import { useEffect, useState } from "react";
import type { Key } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Col,
  Divider,
  Empty,
  InputNumber,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import {
  CloudUploadOutlined,
  DeleteOutlined,
  ProfileOutlined,
  ReloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { PdfPreviewModal } from "../components/PdfPreviewModal";
import { SectionTreeViewer, findFirstSection, getSectionTreeKeys } from "../components/SectionTreeViewer";
import {
  createChapterProfileJob,
  deleteDocument,
  getDocumentSections,
  getSectionParseModeLabel,
  listChapterProfileJobs,
  listDocuments,
  listParseJobs,
  parseDocument,
  parseDocumentsBatch,
  SECTION_PARSE_MODE_OPTIONS,
  type ChapterProfileGenerationJob,
  type DocumentParseResult,
  type DocumentRecord,
  type DocumentType,
  type ParseJobRecord,
  type ParseResultSummary,
  type PlanSection,
  type SectionParseMode,
  uploadDocument,
} from "../services/documentService";
import { fetchPdfPreviewUrl } from "../services/filePreviewService";

type ParsedDocumentUploadPageProps = {
  documentType: DocumentType;
  title: string;
  uploadCardTitle: string;
  emptyDescription: string;
  enableChapterProfiles?: boolean;
};

const DEFAULT_PARSE_CONCURRENCY = 3;
const DEFAULT_PROFILE_CONCURRENCY = 6;

const ParsedDocumentUploadPage = ({
  documentType,
  title,
  uploadCardTitle,
  emptyDescription,
  enableChapterProfiles = false,
}: ParsedDocumentUploadPageProps) => {
  const navigate = useNavigate();
  const [files, setFiles] = useState<DocumentRecord[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [parsed, setParsed] = useState<DocumentParseResult | null>(null);
  const [parseJobs, setParseJobs] = useState<ParseJobRecord[]>([]);
  const [selectedSection, setSelectedSection] = useState<PlanSection | null>(null);
  const [expandedSectionKeys, setExpandedSectionKeys] = useState<string[]>([]);
  const [profileJobs, setProfileJobs] = useState<Record<string, ChapterProfileGenerationJob>>({});
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [activeParseMode, setActiveParseMode] = useState<SectionParseMode>("docling_auto");
  const [parseConcurrency, setParseConcurrency] = useState(DEFAULT_PARSE_CONCURRENCY);
  const [profileConcurrency, setProfileConcurrency] = useState(DEFAULT_PROFILE_CONCURRENCY);
  const [loading, setLoading] = useState({
    files: false,
    upload: false,
    delete: false,
    parse: false,
    profile: false,
    view: false,
  });
  const [pdfPreview, setPdfPreview] = useState({ open: false, title: "", url: "" });
  const selectedFile = selectedFileId !== null ? files.find((file) => file.id === selectedFileId) ?? null : null;

  const refreshFiles = async () => {
    setLoading((s) => ({ ...s, files: true }));
    try {
      setFiles(await listDocuments({ document_type: documentType }));
    } catch {
      message.error("Failed to load file list.");
    } finally {
      setLoading((s) => ({ ...s, files: false }));
    }
  };

  const refreshParseJobs = async () => {
    try {
      setParseJobs(await listParseJobs({ document_type: documentType, limit: 20 }));
    } catch (error: unknown) {
      const detail = getErrorDetail(error);
      if (detail) {
        message.warning(detail);
      }
      setParseJobs([]);
    }
  };

  const refreshProfileJobs = async () => {
    if (!enableChapterProfiles) {
      return;
    }
    try {
      const result = await listChapterProfileJobs({ page: 1, page_size: 200 });
      const latest: Record<string, ChapterProfileGenerationJob> = {};
      for (const job of result.items) {
        const key = getProfileJobKey(job.document_id);
        if (!latest[key]) {
          latest[key] = job;
        }
      }
      setProfileJobs(latest);
    } catch {
      message.error("Failed to load chapter profile jobs.");
    }
  };

  useEffect(() => {
    void refreshFiles();
    void refreshParseJobs();
    void refreshProfileJobs();
  }, []);

  useEffect(() => {
    if (!files.length) {
      if (selectedFileId !== null) {
        setSelectedFileId(null);
        setParsed(null);
        setSelectedSection(null);
        setExpandedSectionKeys([]);
      }
      return;
    }
    if (selectedFileId !== null && files.some((file) => file.id === selectedFileId)) {
      return;
    }
    const firstFile = files[0];
    setSelectedFileId(firstFile.id);
    void handleView(firstFile.id, activeParseMode, { silent: true });
  }, [files, selectedFileId, activeParseMode]);

  const handleUpload = async () => {
    const originFiles = fileList.map((item) => item.originFileObj).filter(Boolean) as File[];
    if (!originFiles.length) {
      message.warning("Select a Word, Excel, PDF, or image file first.");
      return;
    }
    setLoading((s) => ({ ...s, upload: true }));
    try {
      for (const file of originFiles) {
        await uploadDocument(file, documentType, {
          sectionParseMode: file.name.toLowerCase().endsWith(".docx") ? activeParseMode : undefined,
        });
      }
      message.success(`${originFiles.length} file(s) uploaded. Parsing started.`);
      setFileList([]);
      await Promise.all([refreshFiles(), refreshParseJobs()]);
    } catch {
      message.error("Upload failed.");
    } finally {
      setLoading((s) => ({ ...s, upload: false }));
    }
  };

  const handleView = async (
    id: number,
    mode: SectionParseMode = activeParseMode,
    options: { silent?: boolean } = {},
  ) => {
    setLoading((s) => ({ ...s, view: true }));
    try {
      const result = await getDocumentSections(id, mode);
      setParsed(result);
      setExpandedSectionKeys(getSectionTreeKeys(result.sections));
      setSelectedSection(findFirstSection(result.sections));
    } catch {
      if (!options.silent) {
        message.error("Failed to load sections.");
      }
    } finally {
      setLoading((s) => ({ ...s, view: false }));
    }
  };

  const handleParse = async (record: DocumentRecord, mode: SectionParseMode) => {
    const result = findParseResult(record, mode);
    if (isParseRunning(record.id, mode, parseJobs)) {
      message.warning("该文档的当前解析方法已在队列中，请等待完成。");
      return;
    }

    const submit = async () => {
      setLoading((s) => ({ ...s, parse: true }));
      try {
        await parseDocument(record.id, mode);
        message.success(`${result?.parse_status === "parsed" ? "Reparse" : "Parse"} 已加入解析队列。`);
        await Promise.all([refreshFiles(), refreshParseJobs()]);
      } catch (error: unknown) {
        message.error(getErrorDetail(error) ?? "解析任务提交失败。");
      } finally {
        setLoading((s) => ({ ...s, parse: false }));
      }
    };

    if (result?.parse_status === "parsed") {
      Modal.confirm({
        title: "Re-parse this result?",
        content: `将只重跑 ${getSectionParseModeLabel(mode)}，不会覆盖其他解析方法的结果。`,
        okText: "Re-parse",
        okType: "danger",
        cancelText: "Cancel",
        onOk: submit,
      });
      return;
    }
    await submit();
  };

  const handleBatchParse = async () => {
    const ids = selectedRowKeys.map(Number).filter(Boolean);
    if (!ids.length) {
      message.warning("请先选择要解析的文档。");
      return;
    }
    setLoading((s) => ({ ...s, parse: true }));
    try {
      const jobs = await parseDocumentsBatch({
        document_ids: ids,
        section_parse_modes: [activeParseMode],
        concurrency: parseConcurrency,
      });
      message.success(`${jobs.length} 个解析任务已加入队列，并发数 ${parseConcurrency}。`);
      await Promise.all([refreshFiles(), refreshParseJobs()]);
    } catch (error: unknown) {
      message.error(getErrorDetail(error) ?? "批量解析任务提交失败。");
    } finally {
      setLoading((s) => ({ ...s, parse: false }));
    }
  };

  const handleDelete = async (record: DocumentRecord) => {
    setLoading((s) => ({ ...s, delete: true }));
    try {
      await deleteDocument(record.id);
      message.success("Document deleted.");
      if (parsed?.id === record.id) {
        setParsed(null);
        setSelectedSection(null);
        setExpandedSectionKeys([]);
        setSelectedFileId(null);
      }
      await Promise.all([refreshFiles(), refreshParseJobs(), refreshProfileJobs()]);
    } catch {
      message.error("Delete failed.");
    } finally {
      setLoading((s) => ({ ...s, delete: false }));
    }
  };

  const handlePreviewPdf = async (record: DocumentRecord) => {
    try {
      const url = await fetchPdfPreviewUrl(`/documents/${record.id}/preview`);
      setPdfPreview({ open: true, title: record.file_name, url });
    } catch {
      message.error("PDF preview failed.");
    }
  };

  const handleRowClick = async (record: DocumentRecord) => {
    setSelectedFileId(record.id);
    await handleView(record.id, activeParseMode);
  };

  const handleModeChange = async (mode: SectionParseMode) => {
    setActiveParseMode(mode);
    if (selectedFileId !== null) {
      await handleView(selectedFileId, mode);
    }
  };

  const handleCreateProfileJob = async (record: DocumentRecord) => {
    const result = findParseResult(record, activeParseMode);
    if (result?.parse_status !== "parsed") {
      message.warning("Parse the active result before generating chapter profiles.");
      return;
    }
    setLoading((s) => ({ ...s, profile: true }));
    try {
      const job = await createChapterProfileJob(record.id, activeParseMode, profileConcurrency);
      message.success(`Chapter profile job #${job.id} queued.`);
      await refreshProfileJobs();
      navigate(`/construction-plan/profile-jobs/${job.id}`);
    } catch {
      message.error("Failed to create chapter profile job.");
    } finally {
      setLoading((s) => ({ ...s, profile: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{title}</h1>
        <Button
          icon={<ReloadOutlined />}
          loading={loading.files}
          onClick={() => void Promise.all([refreshFiles(), refreshParseJobs(), refreshProfileJobs()])}
        >
          Refresh
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title={uploadCardTitle}>
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Upload
                beforeUpload={() => false}
                fileList={fileList}
                multiple
                accept=".docx,.xlsx,.csv,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
                onChange={({ fileList: next }) => setFileList(next)}
              >
                <Button icon={<CloudUploadOutlined />}>Select Document Files</Button>
              </Upload>
              <ParseControls
                activeParseMode={activeParseMode}
                parseConcurrency={parseConcurrency}
                profileConcurrency={profileConcurrency}
                enableChapterProfiles={enableChapterProfiles}
                onModeChange={(mode) => void handleModeChange(mode)}
                onConcurrencyChange={setParseConcurrency}
                onProfileConcurrencyChange={setProfileConcurrency}
              />
              <Button type="primary" loading={loading.upload} onClick={() => void handleUpload()} icon={<CloudUploadOutlined />}>
                Upload to MinIO
              </Button>
            </Space>

            <Divider />

            <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
              <Typography.Text strong>Uploaded Files</Typography.Text>
              <Button
                size="small"
                icon={<SyncOutlined />}
                loading={loading.parse}
                disabled={!selectedRowKeys.length}
                onClick={() => void handleBatchParse()}
              >
                Parse Selected
              </Button>
            </Space>
            <Table<DocumentRecord>
              rowKey="id"
              size="small"
              style={{ marginTop: 12 }}
              dataSource={files}
              rowSelection={{
                selectedRowKeys,
                onChange: setSelectedRowKeys,
              }}
              onRow={(record) => ({
                onClick: () => void handleRowClick(record),
                className: `document-row${selectedFileId === record.id ? " document-row-selected" : ""}`,
              })}
              pagination={{ pageSize: 8 }}
              columns={[
                {
                  title: "File Name",
                  dataIndex: "file_name",
                  ellipsis: true,
                  render: (value: string, record) =>
                    isPdf(value) ? (
                      <Button
                        type="link"
                        size="small"
                        className="table-link-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handlePreviewPdf(record);
                        }}
                      >
                        {value}
                      </Button>
                    ) : (
                      value
                    ),
                },
                {
                  title: "Results",
                  width: 112,
                  render: (_, record) => <ResultSummaryTag record={record} />,
                },
                {
                  title: "Active Mode",
                  width: 128,
                  render: (_, record) => <ParseStatusTag status={findParseResult(record, activeParseMode)?.parse_status ?? "uploaded"} />,
                },
                {
                  title: "Size",
                  dataIndex: "file_size",
                  width: 92,
                  render: (v: number) => formatFileSize(v),
                },
                {
                  title: "",
                  width: enableChapterProfiles ? 292 : 172,
                  render: (_, record) => {
                    const result = findParseResult(record, activeParseMode);
                    const running = isParseRunning(record.id, activeParseMode, parseJobs);
                    const profileJob = profileJobs[getProfileJobKey(record.id)];
                    return (
                      <Space size={6} wrap onClick={(e) => e.stopPropagation()}>
                        <Button
                          size="small"
                          icon={running ? <SyncOutlined spin /> : <ReloadOutlined />}
                          loading={loading.parse && selectedFileId === record.id}
                          disabled={running}
                          onClick={() => void handleParse(record, activeParseMode)}
                        >
                          {running ? "Parsing..." : result?.parse_status === "parsed" ? "Reparse" : result?.parse_status === "failed" ? "Retry" : "Parse"}
                        </Button>
                        {enableChapterProfiles ? (
                          <>
                            <Button
                              size="small"
                              icon={<ProfileOutlined />}
                              loading={loading.profile}
                              disabled={result?.parse_status !== "parsed"}
                              onClick={() => void handleCreateProfileJob(record)}
                            >
                              Profile
                            </Button>
                            {profileJob ? (
                              <Button
                                size="small"
                                type="link"
                                className="table-link-button"
                                title="Profile queue"
                                onClick={() => navigate(`/construction-plan/profile-jobs/${profileJob.id}`)}
                              >
                                <Space size={4}>
                                  <ProfileStatusTag status={profileJob.status} />
                                  <span>
                                    {profileJob.processed_sections}/{profileJob.total_sections}
                                  </span>
                                </Space>
                              </Button>
                            ) : null}
                          </>
                        ) : null}
                        <Popconfirm
                          title="Delete this document?"
                          description="The uploaded file and parsed sections will be removed."
                          okText="Delete"
                          okButtonProps={{ danger: true }}
                          onConfirm={() => void handleDelete(record)}
                        >
                          <Button size="small" danger icon={<DeleteOutlined />} loading={loading.delete}>
                            Delete
                          </Button>
                        </Popconfirm>
                      </Space>
                    );
                  },
                },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card
            title={parsed ? `Sections — ${parsed.file_name}` : "Sections"}
            extra={
              parsed ? (
                <Space>
                  <ParseStatusTag status={parsed.parse_status} />
                  <Tag color="purple">{getSectionParseModeLabel(parsed.section_parse_mode)}</Tag>
                </Space>
              ) : null
            }
          >
            <ParseProgressPanel jobs={parseJobs} />
            <Tabs
              activeKey={activeParseMode}
              items={SECTION_PARSE_MODE_OPTIONS.map((item) => ({
                key: item.mode,
                label: item.label,
              }))}
              onChange={(key) => void handleModeChange(key as SectionParseMode)}
            />
            <Spin spinning={loading.view}>
              {parsed ? (
                <SectionsViewer
                  parsed={parsed}
                  selectedSection={selectedSection}
                  expandedKeys={expandedSectionKeys}
                  onExpand={setExpandedSectionKeys}
                  onSelectSection={setSelectedSection}
                />
              ) : (
                <Typography.Text type="secondary">{emptyDescription}</Typography.Text>
              )}
            </Spin>
          </Card>
        </Col>
      </Row>
      <PdfPreviewModal
        title={pdfPreview.title}
        url={pdfPreview.url}
        open={pdfPreview.open}
        onClose={() => setPdfPreview({ open: false, title: "", url: "" })}
      />
    </div>
  );
};

const ParseControls = ({
  activeParseMode,
  parseConcurrency,
  profileConcurrency,
  enableChapterProfiles,
  onModeChange,
  onConcurrencyChange,
  onProfileConcurrencyChange,
}: {
  activeParseMode: SectionParseMode;
  parseConcurrency: number;
  profileConcurrency: number;
  enableChapterProfiles: boolean;
  onModeChange: (mode: SectionParseMode) => void;
  onConcurrencyChange: (value: number) => void;
  onProfileConcurrencyChange: (value: number) => void;
}) => (
  <Row gutter={[8, 8]}>
    <Col span={enableChapterProfiles ? 12 : 16}>
      <Typography.Text type="secondary">解析方法</Typography.Text>
      <Select
        style={{ width: "100%", marginTop: 4 }}
        value={activeParseMode}
        options={SECTION_PARSE_MODE_OPTIONS.map((item) => ({
          value: item.mode,
          label: item.label,
          title: item.description,
        }))}
        onChange={onModeChange}
      />
    </Col>
    <Col span={enableChapterProfiles ? 6 : 8}>
      <Typography.Text type="secondary">同时解析数</Typography.Text>
      <InputNumber
        min={1}
        max={8}
        value={parseConcurrency}
        style={{ width: "100%", marginTop: 4 }}
        onChange={(value) => onConcurrencyChange(Number(value || DEFAULT_PARSE_CONCURRENCY))}
      />
    </Col>
    {enableChapterProfiles ? (
      <Col span={6}>
        <Typography.Text type="secondary">Profile并发数</Typography.Text>
        <InputNumber
          min={1}
          max={8}
          value={profileConcurrency}
          style={{ width: "100%", marginTop: 4 }}
          onChange={(value) => onProfileConcurrencyChange(Number(value || DEFAULT_PROFILE_CONCURRENCY))}
        />
      </Col>
    ) : null}
  </Row>
);

const SectionsViewer = ({
  parsed,
  selectedSection,
  expandedKeys,
  onExpand,
  onSelectSection,
}: {
  parsed: DocumentParseResult;
  selectedSection: PlanSection | null;
  expandedKeys: string[];
  onExpand: (keys: string[]) => void;
  onSelectSection: (section: PlanSection | null) => void;
}) => {
  if (!parsed.sections.length) {
    return <Empty description={parsed.parse_status === "uploaded" ? "该方法尚未解析。" : "No sections found in this result."} />;
  }
  return (
    <SectionTreeViewer
      sections={parsed.sections}
      selectedSection={selectedSection}
      expandedKeys={expandedKeys}
      onExpand={onExpand}
      onSelectSection={onSelectSection}
    />
  );
};

export const TemplateUploadPage = () => (
  <ParsedDocumentUploadPage
    documentType="template"
    title="Upload Templates"
    uploadCardTitle="Upload Template Document"
    emptyDescription="Click a document row on the left to view its parsed sections here."
  />
);

export const ConstructionPlanReviewPage = () => (
  <ParsedDocumentUploadPage
    documentType="construction_plan"
    title="Upload Construction Plan"
    uploadCardTitle="Upload Construction Plan Document"
    emptyDescription="Click a document row on the left to view its parsed sections here."
    enableChapterProfiles
  />
);

const findParseResult = (record: DocumentRecord, mode: SectionParseMode): ParseResultSummary | undefined =>
  record.parse_results.find((result) => result.section_parse_mode === mode);

const isParseRunning = (documentId: number, mode: SectionParseMode, jobs: ParseJobRecord[]) =>
  jobs.some((job) => job.document_id === documentId && job.section_parse_mode === mode && (job.status === "queued" || job.status === "running"));

const getProfileJobKey = (documentId: number) => String(documentId);

const ResultSummaryTag = ({ record }: { record: DocumentRecord }) => {
  const parsedCount = record.parse_results.filter((result) => result.parse_status === "parsed").length;
  return <Tag color={parsedCount ? "green" : "default"}>{parsedCount}/{SECTION_PARSE_MODE_OPTIONS.length} parsed</Tag>;
};

const formatFileSize = (size: number) => {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
};

const isPdf = (fileName: string) => fileName.toLowerCase().endsWith(".pdf");

const ParseProgressPanel = ({ jobs }: { jobs: ParseJobRecord[] }) => {
  const recent = jobs.slice(0, 6);
  if (!recent.length) {
    return null;
  }
  return (
    <div className="parse-progress-panel">
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Typography.Text strong>近期解析任务</Typography.Text>
        {recent.map((job) => (
          <div className="parse-job-row" key={job.id}>
            <Space wrap>
              <Tag>{job.file_name}</Tag>
              <Tag color="purple">{getSectionParseModeLabel(job.section_parse_mode)}</Tag>
              <Tag>{job.job_type}</Tag>
              <ParseStatusTag status={job.status} />
            </Space>
            <Progress
              size="small"
              percent={Math.max(0, Math.min(job.progress ?? 0, 100))}
              status={job.status === "failed" ? "exception" : job.status === "success" ? "success" : job.status === "running" ? "active" : "normal"}
            />
          </div>
        ))}
      </Space>
    </div>
  );
};

const ParseStatusTag = ({ status }: { status: string }) => {
  const color = status === "parsed" || status === "success" ? "green" : status === "failed" ? "red" : status === "queued" ? "gold" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const ProfileStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success" ? "green" : status === "partial_success" ? "gold" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const getErrorDetail = (error: unknown) =>
  typeof error === "object" &&
  error !== null &&
  "response" in error &&
  typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === "string"
    ? (error as { response: { data: { detail: string } } }).response.data.detail
    : null;
