import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Select,
  Table,
  Tag,
  Tree,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  CloudUploadOutlined,
  DeleteOutlined,
  ProfileOutlined,
  ReloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { PdfPreviewModal } from "../components/PdfPreviewModal";
import {
  deleteDocument,
  createChapterProfileJob,
  type DocumentType,
  type ChapterProfileGenerationJob,
  getDocumentSections,
  listChapterProfileJobs,
  listDocuments,
  listSectionParseModes,
  parseDocument,
  type PlanSection,
  type SectionParseMode,
  type SectionParseModeItem,
  uploadDocument,
  type DocumentParseResult,
  type DocumentRecord,
} from "../services/documentService";
import { fetchPdfPreviewUrl } from "../services/filePreviewService";

type DocumentUploadReviewProps = {
  documentType: DocumentType;
  title: string;
  uploadCardTitle: string;
  emptyDescription: string;
};

const DocumentUploadReviewPage = ({
  documentType,
  title,
  uploadCardTitle,
  emptyDescription,
}: DocumentUploadReviewProps) => {
  const navigate = useNavigate();
  const [files, setFiles] = useState<DocumentRecord[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [parsed, setParsed] = useState<DocumentParseResult | null>(null);
  const [selectedSection, setSelectedSection] = useState<PlanSection | null>(null);
  const [profileJobs, setProfileJobs] = useState<Record<number, ChapterProfileGenerationJob>>({});
  const [loading, setLoading] = useState({ files: false, upload: false, delete: false, profile: false });
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [parsingFileId, setParsingFileId] = useState<number | null>(null);
  const [viewingFileId, setViewingFileId] = useState<number | null>(null);
  const [pdfPreview, setPdfPreview] = useState({ open: false, title: "", url: "" });
  const [sectionParseModes, setSectionParseModes] = useState<SectionParseModeItem[]>([]);
  const [sectionParseMode, setSectionParseMode] = useState<SectionParseMode>("docling_auto");
  const enableChapterProfiles = documentType === "construction_plan";

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

  const refreshProfileJobs = async () => {
    if (!enableChapterProfiles) {
      return;
    }
    try {
      const result = await listChapterProfileJobs({ page: 1, page_size: 200 });
      const latest: Record<number, ChapterProfileGenerationJob> = {};
      for (const job of result.items) {
        if (!latest[job.document_id]) {
          latest[job.document_id] = job;
        }
      }
      setProfileJobs(latest);
    } catch {
      message.error("Failed to load chapter profile jobs.");
    }
  };

  useEffect(() => {
    void refreshFiles();
    void refreshProfileJobs();
    if (enableChapterProfiles) {
      void listSectionParseModes()
        .then(setSectionParseModes)
        .catch(() => message.error("Failed to load section parse modes."));
    }
  }, []);

  useEffect(() => {
    const hasParsingFile = files.some((file) => file.parse_status === "uploaded" || file.parse_status === "parsing");
    const hasRunningProfileJob = Object.values(profileJobs).some((job) => job.status === "queued" || job.status === "running");
    if (!hasParsingFile && !hasRunningProfileJob) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshFiles();
      void refreshProfileJobs();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [files, profileJobs]);

  const handleUpload = async () => {
    const originFile = fileList[0]?.originFileObj;
    if (!originFile) {
      message.warning("Select a Word, Excel, PDF, or image file first.");
      return;
    }
    const isDocx = originFile.name.toLowerCase().endsWith(".docx");
    setLoading((s) => ({ ...s, upload: true }));
    try {
      const result = await uploadDocument(originFile, documentType, {
        sectionParseMode: enableChapterProfiles && isDocx ? sectionParseMode : undefined,
      });
      message.success(`Uploaded: ${result.file_name}. Parsing started.`);
      setFileList([]);
      await refreshFiles();
    } catch {
      message.error("Upload failed.");
    } finally {
      setLoading((s) => ({ ...s, upload: false }));
    }
  };

  const selectFirstSection = (result: DocumentParseResult) => {
    const first = findFirstSection(result.sections);
    setSelectedSection(first);
  };

  const handleView = async (id: number) => {
    setViewingFileId(id);
    try {
      const result = await getDocumentSections(id);
      setParsed(result);
      selectFirstSection(result);
    } catch {
      message.error("Failed to load sections.");
    } finally {
      setViewingFileId(null);
    }
  };

  const handleParse = async (record: DocumentRecord) => {
    if (record.parse_status === "parsed") {
      Modal.confirm({
        title: "Re-parse this document?",
        content: "Re-parsing will delete existing parsed sections and rebuild them.",
        okText: "Re-parse",
        okType: "danger",
        cancelText: "Cancel",
        onOk: async () => {
          await executeParse(record);
        },
      });
      return;
    }
    await executeParse(record);
  };

  const executeParse = async (record: DocumentRecord) => {
    setParsingFileId(record.id);
    const reparseMode =
      enableChapterProfiles && record.file_name.toLowerCase().endsWith(".docx")
        ? record.section_parse_mode || sectionParseMode
        : undefined;
    try {
      const result = await parseDocument(record.id, reparseMode);
      setParsed(result);
      selectFirstSection(result);
      setSelectedFileId(record.id);
      await refreshFiles();
    } catch {
      message.error("Parse failed.");
    } finally {
      setParsingFileId(null);
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
        setSelectedFileId(null);
      }
      await refreshFiles();
      await refreshProfileJobs();
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
    if (record.parse_status === "uploaded" || record.parse_status === "parsing") {
      message.info("This document hasn't been parsed yet. Click 'Parse' to start.");
      return;
    }
    if (record.parse_status === "failed") {
      message.warning("Parsing failed for this document. Click 'Retry' to try again.");
      return;
    }
    await handleView(record.id);
  };

  const handleCreateProfileJob = async (record: DocumentRecord) => {
    if (record.parse_status !== "parsed") {
      message.warning("Parse the document before generating chapter profiles.");
      return;
    }
    setLoading((s) => ({ ...s, profile: true }));
    try {
      const job = await createChapterProfileJob(record.id);
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
        <Button icon={<ReloadOutlined />} loading={loading.files} onClick={() => void refreshFiles()}>
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
                maxCount={1}
                accept=".docx,.xlsx,.csv,.pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
                onChange={({ fileList: next }) => setFileList(next)}
              >
                <Button icon={<CloudUploadOutlined />}>Select Document File</Button>
              </Upload>
              {enableChapterProfiles ? (
                <div>
                  <Typography.Text type="secondary">Word 分章策略（仅 .docx）</Typography.Text>
                  <Select
                    style={{ width: "100%", marginTop: 4 }}
                    value={sectionParseMode}
                    options={
                      sectionParseModes.length
                        ? sectionParseModes.map((item) => ({
                            value: item.mode,
                            label: item.label,
                            title: item.description,
                          }))
                        : [{ value: "docling_auto", label: "Docling 线性分章（原方案）" }]
                    }
                    onChange={(value) => setSectionParseMode(value)}
                  />
                </div>
              ) : null}
              <Button
                type="primary"
                loading={loading.upload}
                onClick={() => void handleUpload()}
                icon={<CloudUploadOutlined />}
              >
                Upload to MinIO
              </Button>
            </Space>

            <Divider />

            <Typography.Text strong>Uploaded Files</Typography.Text>
            <Table<DocumentRecord>
              rowKey="id"
              size="small"
              style={{ marginTop: 12 }}
              dataSource={files}
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
                      <Button type="link" size="small" className="table-link-button" onClick={(e) => {
                        e.stopPropagation();
                        void handlePreviewPdf(record);
                      }}>
                        {value}
                      </Button>
                    ) : (
                      value
                    ),
                },
                {
                  title: "Status",
                  dataIndex: "parse_status",
                  width: 92,
                  render: (v: string) => <ParseStatusTag status={v} />,
                },
                ...(enableChapterProfiles
                  ? [
                      {
                        title: "Parse Mode",
                        dataIndex: "section_parse_mode",
                        width: 130,
                        ellipsis: true,
                        render: (v: string) => sectionParseModes.find((m) => m.mode === v)?.label ?? v,
                      },
                    ]
                  : []),
                {
                  title: "Size",
                  dataIndex: "file_size",
                  width: 92,
                  render: (v: number) => formatFileSize(v),
                },
                {
                  title: "Created At",
                  dataIndex: "created_at",
                  width: 170,
                  render: (v: string) => (v ? new Date(v).toLocaleString() : "-"),
                },
                {
                  title: "",
                  width: enableChapterProfiles ? 300 : 160,
                  render: (_, record) => (
                    <Space size={6} wrap onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="small"
                        icon={
                          record.parse_status === "parsing" ? (
                            <SyncOutlined spin />
                          ) : (
                            <ReloadOutlined />
                          )
                        }
                        loading={parsingFileId === record.id}
                        disabled={record.parse_status === "parsing"}
                        onClick={() => void handleParse(record)}
                      >
                        {record.parse_status === "parsing"
                          ? "Parsing..."
                          : record.parse_status === "parsed"
                            ? "Re-parse"
                            : record.parse_status === "failed"
                              ? "Retry"
                              : "Parse"}
                      </Button>
                      {enableChapterProfiles ? (
                        <>
                          <Button
                            size="small"
                            icon={<ProfileOutlined />}
                            loading={loading.profile}
                            disabled={record.parse_status !== "parsed"}
                            onClick={() => void handleCreateProfileJob(record)}
                          >
                            Profile
                          </Button>
                          {profileJobs[record.id] ? (
                            <Button
                              size="small"
                              type="link"
                              className="table-link-button"
                              onClick={() => navigate(`/construction-plan/profile-jobs/${profileJobs[record.id].id}`)}
                            >
                              <Space size={4}>
                                <ProfileStatusTag status={profileJobs[record.id].status} />
                                <span>
                                  {profileJobs[record.id].processed_sections}/{profileJobs[record.id].total_sections}
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
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card title={parsed ? `Sections — ${parsed.file_name}` : "Sections"}>
            <Spin spinning={viewingFileId !== null}>
            {parsed ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Space wrap>
                  <Tag color="blue">{parsed.file_name}</Tag>
                  <ParseStatusTag status={parsed.parse_status} />
                  {enableChapterProfiles ? (
                    <Tag>
                      {sectionParseModes.find((m) => m.mode === parsed.section_parse_mode)?.label ??
                        parsed.section_parse_mode}
                    </Tag>
                  ) : null}
                </Space>
                {parsed.sections.length ? (
                  <Row gutter={[16, 16]}>
                    <Col xs={24} lg={10}>
                      <div className="plan-section-tree">
                        <Tree
                          blockNode
                          defaultExpandAll
                          selectedKeys={selectedSection ? [String(selectedSection.id)] : []}
                          treeData={toTreeData(parsed.sections)}
                          onSelect={(keys) => {
                            const key = keys[0];
                            if (!key) {
                              return;
                            }
                            setSelectedSection(findSection(parsed.sections, Number(key)));
                          }}
                        />
                      </div>
                    </Col>
                    <Col xs={24} lg={14}>
                      <div className="plan-section-content">
                        {selectedSection ? (
                          <>
                            <Typography.Title level={4}>{selectedSection.title}</Typography.Title>
                            <Typography.Paragraph>
                              {selectedSection.content || "No content found for this section."}
                            </Typography.Paragraph>
                          </>
                        ) : (
                          <Empty description="Select a section" />
                        )}
                      </div>
                    </Col>
                  </Row>
                ) : (
                  <Empty description="No sections found in this document." />
                )}
              </Space>
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

export const TemplateUploadPage = () => (
  <DocumentUploadReviewPage
    documentType="template"
    title="Upload Templates"
    uploadCardTitle="Upload Template Document"
    emptyDescription="Click a document row on the left to view its parsed sections here."
  />
);

export const ConstructionPlanReviewPage = () => (
  <DocumentUploadReviewPage
    documentType="construction_plan"
    title="Upload Construction Plan"
    uploadCardTitle="Upload Construction Plan Document"
    emptyDescription="Click a document row on the left to view its parsed sections here."
  />
);

const toTreeData = (sections: PlanSection[]): DataNode[] =>
  sections.map((section) => ({
    key: String(section.id),
    title: section.title,
    children: toTreeData(section.children),
  }));

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

const ParseStatusTag = ({ status }: { status: string }) => {
  const color = status === "parsed" ? "green" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const ProfileStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success" ? "green" : status === "partial_success" ? "gold" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};
