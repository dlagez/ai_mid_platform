import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Divider,
  Empty,
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
  FileTextOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { PdfPreviewModal } from "../components/PdfPreviewModal";
import {
  getDocumentSections,
  listDocuments,
  parseDocument,
  type PlanSection,
  uploadDocument,
  type DocumentParseResult,
  type DocumentRecord,
} from "../services/documentService";
import { fetchPdfPreviewUrl } from "../services/filePreviewService";

export const ConstructionPlanReviewPage = () => {
  const [files, setFiles] = useState<DocumentRecord[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [parsed, setParsed] = useState<DocumentParseResult | null>(null);
  const [selectedSection, setSelectedSection] = useState<PlanSection | null>(null);
  const [loading, setLoading] = useState({ files: false, upload: false, parse: false });
  const [pdfPreview, setPdfPreview] = useState({ open: false, title: "", url: "" });

  const refreshFiles = async () => {
    setLoading((s) => ({ ...s, files: true }));
    try {
      setFiles(await listDocuments());
    } catch {
      message.error("Failed to load file list.");
    } finally {
      setLoading((s) => ({ ...s, files: false }));
    }
  };

  useEffect(() => {
    void refreshFiles();
  }, []);

  useEffect(() => {
    const hasParsingFile = files.some((file) => file.parse_status === "uploaded" || file.parse_status === "parsing");
    if (!hasParsingFile) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshFiles();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [files]);

  const handleUpload = async () => {
    const originFile = fileList[0]?.originFileObj;
    if (!originFile) {
      message.warning("Select a Word, Excel, PDF, or image file first.");
      return;
    }
    setLoading((s) => ({ ...s, upload: true }));
    try {
      const result = await uploadDocument(originFile);
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

  const handlePreviewPdf = async (record: DocumentRecord) => {
    try {
      const url = await fetchPdfPreviewUrl(`/documents/${record.id}/preview`);
      setPdfPreview({ open: true, title: record.file_name, url });
    } catch {
      message.error("PDF preview failed.");
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Review of Construction Plan</h1>
        <Button icon={<ReloadOutlined />} loading={loading.files} onClick={() => void refreshFiles()}>
          Refresh
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="Upload Document">
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
                  width: 150,
                  render: (_, record) => (
                    <Space size={6}>
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
              <Typography.Text type="secondary">
                Upload a .docx file, then view the parsed section tree and content.
              </Typography.Text>
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
