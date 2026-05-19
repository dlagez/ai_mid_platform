import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Empty,
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
  EyeOutlined,
  FileMarkdownOutlined,
  InboxOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import {
  getPPOcrMarkdown,
  listPPOcrRecords,
  parsePPOcrFile,
  type UtilityParseRecord,
} from "../services/utilsService";

export const UtilsPPOcrPage = () => {
  const [records, setRecords] = useState<UtilityParseRecord[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<UtilityParseRecord | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState({ records: false, parse: false, markdown: false });

  const refreshRecords = async () => {
    setLoading((s) => ({ ...s, records: true }));
    try {
      setRecords(await listPPOcrRecords());
    } catch {
      message.error("Failed to load PPOCR records.");
    } finally {
      setLoading((s) => ({ ...s, records: false }));
    }
  };

  useEffect(() => {
    void refreshRecords();
  }, []);

  const handleParse = async () => {
    const originFile = fileList[0]?.originFileObj;
    if (!originFile) {
      message.warning("Select a PDF or image file first.");
      return;
    }
    setLoading((s) => ({ ...s, parse: true }));
    try {
      const result = await parsePPOcrFile(originFile);
      setSelectedRecord(result.record);
      setMarkdown(result.markdown);
      setFileList([]);
      await refreshRecords();
      message.success("PPOCR parse completed.");
    } catch {
      message.error("PPOCR parse failed.");
      await refreshRecords();
    } finally {
      setLoading((s) => ({ ...s, parse: false }));
    }
  };

  const handleViewMarkdown = async (record: UtilityParseRecord) => {
    setLoading((s) => ({ ...s, markdown: true }));
    try {
      const result = await getPPOcrMarkdown(record.id);
      setSelectedRecord(result.record);
      setMarkdown(result.markdown);
    } catch {
      message.error("Failed to load markdown.");
    } finally {
      setLoading((s) => ({ ...s, markdown: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>PPOCR</h1>
        <Button icon={<ReloadOutlined />} loading={loading.records} onClick={() => void refreshRecords()}>
          Refresh
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card title="Upload">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Upload.Dragger
                beforeUpload={() => false}
                fileList={fileList}
                maxCount={1}
                accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
                onChange={({ fileList: next }) => setFileList(next)}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">Select PDF or image</p>
              </Upload.Dragger>
              <Button
                type="primary"
                block
                loading={loading.parse}
                icon={<CloudUploadOutlined />}
                onClick={() => void handleParse()}
              >
                Upload and Parse
              </Button>
            </Space>
          </Card>

          <Card title="Records" style={{ marginTop: 16 }}>
            <Table<UtilityParseRecord>
              rowKey="id"
              size="small"
              loading={loading.records}
              dataSource={records}
              pagination={{ pageSize: 8 }}
              columns={[
                { title: "Source", dataIndex: "source_file_name", ellipsis: true },
                {
                  title: "Status",
                  dataIndex: "parse_status",
                  width: 92,
                  render: (value: string) => <ParseStatusTag status={value} />,
                },
                {
                  title: "Method",
                  dataIndex: "parser_provider",
                  width: 82,
                  render: (value: string) => <Tag color="blue">{value}</Tag>,
                },
                {
                  title: "",
                  width: 86,
                  render: (_, record) => (
                    <Button
                      size="small"
                      icon={<EyeOutlined />}
                      disabled={!record.parsed}
                      loading={loading.markdown && selectedRecord?.id === record.id}
                      onClick={() => void handleViewMarkdown(record)}
                    >
                      View
                    </Button>
                  ),
                },
              ]}
              expandable={{
                expandedRowRender: (record) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text type="secondary">Markdown: {record.parsed_file_name ?? "-"}</Typography.Text>
                    <Typography.Text type="secondary">Uploaded: {formatDate(record.created_at)}</Typography.Text>
                    {record.error_message ? (
                      <Typography.Text type="danger">Error: {record.error_message}</Typography.Text>
                    ) : null}
                  </Space>
                ),
              }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={15}>
          <Card
            title={
              <Space>
                <FileMarkdownOutlined />
                <span>{selectedRecord?.parsed_file_name ?? "Markdown"}</span>
              </Space>
            }
          >
            {markdown ? (
              <pre className="markdown-preview">{markdown}</pre>
            ) : (
              <Empty description="No markdown selected" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

const ParseStatusTag = ({ status }: { status: string }) => {
  const color = status === "parsed" ? "green" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDate = (value: string | null) => {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
};
