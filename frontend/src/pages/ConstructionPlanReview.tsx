import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Divider,
  Row,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import {
  CloudUploadOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  listDocuments,
  parseDocument,
  uploadDocument,
  type DocumentParseResult,
  type DocumentRecord,
} from "../services/documentService";

export const ConstructionPlanReviewPage = () => {
  const [files, setFiles] = useState<DocumentRecord[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [parsed, setParsed] = useState<DocumentParseResult | null>(null);
  const [loading, setLoading] = useState({ files: false, upload: false, parse: false });

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

  const handleUpload = async () => {
    const originFile = fileList[0]?.originFileObj;
    if (!originFile) {
      message.warning("Select a .docx file first.");
      return;
    }
    setLoading((s) => ({ ...s, upload: true }));
    try {
      const result = await uploadDocument(originFile);
      message.success(`Uploaded: ${result.file_name}`);
      setFileList([]);
      await refreshFiles();
    } catch {
      message.error("Upload failed.");
    } finally {
      setLoading((s) => ({ ...s, upload: false }));
    }
  };

  const handleParse = async (id: number) => {
    setLoading((s) => ({ ...s, parse: true }));
    try {
      setParsed(await parseDocument(id));
    } catch {
      message.error("Parse failed.");
    } finally {
      setLoading((s) => ({ ...s, parse: false }));
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
          <Card title="Upload Word Document">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Upload
                beforeUpload={() => false}
                fileList={fileList}
                maxCount={1}
                accept=".docx"
                onChange={({ fileList: next }) => setFileList(next)}
              >
                <Button icon={<CloudUploadOutlined />}>Select .docx File</Button>
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
                { title: "File Name", dataIndex: "file_name", ellipsis: true },
                {
                  title: "Uploaded By",
                  dataIndex: "uploaded_by",
                  width: 100,
                },
                {
                  title: "Uploaded At",
                  dataIndex: "uploaded_at",
                  width: 170,
                  render: (v: string) => (v ? new Date(v).toLocaleString() : "-"),
                },
                {
                  title: "",
                  width: 80,
                  render: (_, record) => (
                    <Button
                      size="small"
                      icon={<FileTextOutlined />}
                      loading={loading.parse}
                      onClick={() => void handleParse(record.id)}
                    >
                      Parse
                    </Button>
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card title="Table of Contents">
            {parsed ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Tag color="blue">{parsed.file_name}</Tag>
                <Typography.Paragraph
                  style={{
                    whiteSpace: "pre-wrap",
                    fontFamily: "monospace",
                    background: "#fafafa",
                    padding: 16,
                    borderRadius: 8,
                    maxHeight: 600,
                    overflow: "auto",
                  }}
                >
                  {parsed.toc_text || "No Table of Contents found in this document."}
                </Typography.Paragraph>
              </Space>
            ) : (
              <Typography.Text type="secondary">
                Upload a .docx file and click "Parse" to see the Table of Contents.
              </Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};
