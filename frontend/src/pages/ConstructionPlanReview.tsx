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
  FileTextOutlined,
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
  parseDocument,
  type PlanSection,
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
  const [loading, setLoading] = useState({ files: false, upload: false, parse: false, delete: false, profile: false });
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [parsingFileId, setParsingFileId] = useState<number | null>(null);
  const [pdfPreview, setPdfPreview] = useState({ open: false, title: "", url: "" });
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
    setLoading((s) => ({ ...s, upload: true }));
    try {
      const result = await uploadDocument(originFile, documentType);
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
    setLoading((s) => ({ ...s, parse: true }));
    try {
      const result = await getDocumentSections(id);
      setParsed(result);
      selectFirstSection(result);
    } catch {
      message.error("Failed to load sections.");
    } finally {
      setLoading((s) => ({ ...s, parse: false }));
    }
  };

  const handleParse = async (id: number) => {
    setLoading((s) => ({ ...s, parse: true }));
    try {
      const result = await parseDocument(id);
      setParsed(result);
      selectFirstSection(result);
      await refreshFiles();
    } catch {
      message.error("Parse failed.");
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
              pagination={{ pageSize: 8 }}
              columns={[
                {
                  title: "File Name",
                  dataIndex: "file_name",
                  ellipsis: true,
                  render: (value: string, record) =>
                    isPdf(value) ? (
                      <Button type="link" size="small" className="table-link-button" onClick={() => void handlePreviewPdf(record)}>
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
                  width: enableChapterProfiles ? 360 : 220,
                  render: (_, record) => (
                    <Space size={6} wrap>
                      <Button
                        size="small"
                        icon={<FileTextOutlined />}
                        loading={loading.parse}
                        onClick={() => void handleView(record.id)}
                      >
                        View
                      </Button>
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        loading={loading.parse}
                        onClick={() => void handleParse(record.id)}
                      >
                        Parse
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
          <Card title="Sections">
            {parsed ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Space>
                  <Tag color="blue">{parsed.file_name}</Tag>
                  <ParseStatusTag status={parsed.parse_status} />
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
    emptyDescription="Upload a template document, then view the parsed section tree and content."
  />
);

export const ConstructionPlanReviewPage = () => (
  <DocumentUploadReviewPage
    documentType="construction_plan"
    title="Upload Construction Plan"
    uploadCardTitle="Upload Construction Plan Document"
    emptyDescription="Upload a construction plan document, then view the parsed section tree and content."
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
