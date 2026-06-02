import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import { EyeOutlined, ReloadOutlined, SendOutlined } from "@ant-design/icons";
import { listPromptTestRecords, testPrompt, type PromptTestRecord } from "../services/modelService";

const sampleText =
  "每根立柱底部应设置垫板，垫板厚度不得小于50mm，支设上层支架时下层支架严禁拆除，且上层支架的立柱位置应与下层支架立柱位置对应。";

type PromptType = "profile_extraction" | "checkpoint";

type PromptTestValues = {
  prompt_type: PromptType;
  text: string;
  model?: string;
  temperature: number;
  max_tokens?: number;
  title?: string;
  standard_name?: string;
  clause_no?: string;
  clause_title?: string;
};

export const PromptTestPage = () => {
  const [form] = Form.useForm<PromptTestValues>();
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [output, setOutput] = useState("");
  const [records, setRecords] = useState<PromptTestRecord[]>([]);
  const [recordTotal, setRecordTotal] = useState(0);
  const [recordPage, setRecordPage] = useState(1);
  const [recordPageSize, setRecordPageSize] = useState(10);
  const [selectedRecord, setSelectedRecord] = useState<PromptTestRecord | null>(null);
  const promptType = Form.useWatch("prompt_type", form);

  const loadRecords = async (page = recordPage, pageSize = recordPageSize) => {
    setHistoryLoading(true);
    try {
      const result = await listPromptTestRecords({ page, page_size: pageSize });
      setRecords(result.items);
      setRecordTotal(result.total);
      setRecordPage(result.page);
      setRecordPageSize(result.page_size);
    } catch {
      message.error("Failed to load prompt test records.");
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    void loadRecords(1, recordPageSize);
  }, []);

  const handleSubmit = async (values: PromptTestValues) => {
    setLoading(true);
    try {
      const result = await testPrompt(values);
      setPrompt(result.prompt || "");
      setOutput(JSON.stringify(result.output, null, 2));
      await loadRecords(1, recordPageSize);
    } catch (error) {
      message.error("Prompt test failed. Confirm backend auth and LiteLLM configuration.");
      await loadRecords(1, recordPageSize);
    } finally {
      setLoading(false);
    }
  };

  const handleHistoryTableChange = (pagination: TablePaginationConfig) => {
    void loadRecords(pagination.current ?? 1, pagination.pageSize ?? 10);
  };

  const formatOutput = (value: unknown) => {
    if (value === null || value === undefined) {
      return "";
    }
    return typeof value === "string" ? value : JSON.stringify(value, null, 2);
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Prompt Test</h1>
      </div>
      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            prompt_type: "profile_extraction",
            text: sampleText,
            temperature: 0.1,
          }}
        >
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="prompt_type" label="Prompt" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: "PROFILE_EXTRACTION_PROMPT", value: "profile_extraction" },
                    { label: "CHECKPOINT_PROMPT", value: "checkpoint" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="model" label="Model">
                <Select
                  allowClear
                  placeholder="Backend default"
                  options={[
                    { label: "Backend default", value: "" },
                    { label: "qwen-max", value: "qwen-max" },
                    { label: "qwen-plus", value: "qwen-plus" },
                    { label: "qwen-turbo", value: "qwen-turbo" },
                    { label: "gpt-4o-mini", value: "gpt-4o-mini" },
                    { label: "gpt-4o", value: "gpt-4o" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="temperature" label="Temperature">
                <InputNumber min={0} max={2} step={0.1} className="full-width-input" />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="max_tokens" label="Max tokens">
                <InputNumber min={1} max={8192} placeholder="Auto" className="full-width-input" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col xs={24} md={promptType === "checkpoint" ? 6 : 24}>
              <Form.Item name="title" label={promptType === "checkpoint" ? "Fallback title" : "Section title"}>
                <Input placeholder={promptType === "checkpoint" ? "Used when clause title is empty" : "测试章节"} />
              </Form.Item>
            </Col>
            {promptType === "checkpoint" && (
              <>
                <Col xs={24} md={6}>
                  <Form.Item name="standard_name" label="Standard name">
                    <Input placeholder="测试规范" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item name="clause_no" label="Clause no">
                    <Input placeholder="6.1.1" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item name="clause_title" label="Clause title">
                    <Input placeholder="测试条文" />
                  </Form.Item>
                </Col>
              </>
            )}
          </Row>

          <Form.Item name="text" label="Input text" rules={[{ required: true }]}>
            <Input.TextArea rows={9} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} icon={<SendOutlined />}>
              Test Prompt
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Space direction="vertical" size={16} className="prompt-test-results">
        <Card title="Output">
          <Typography.Text className="model-output">{output || "LLM output will appear here."}</Typography.Text>
        </Card>
        <Card title="Rendered Prompt">
          <Typography.Text className="model-output">{prompt || "Rendered prompt will appear here."}</Typography.Text>
        </Card>
        <Card
          title="History"
          extra={
            <Button icon={<ReloadOutlined />} loading={historyLoading} onClick={() => void loadRecords()}>
              Refresh
            </Button>
          }
        >
          <Table<PromptTestRecord>
            rowKey="id"
            loading={historyLoading}
            dataSource={records}
            pagination={{
              current: recordPage,
              pageSize: recordPageSize,
              total: recordTotal,
              showSizeChanger: true,
            }}
            onChange={handleHistoryTableChange}
            columns={[
              {
                title: "ID",
                dataIndex: "id",
                width: 88,
              },
              {
                title: "Prompt",
                dataIndex: "prompt_type",
                render: (value: PromptType) =>
                  value === "profile_extraction" ? "PROFILE_EXTRACTION_PROMPT" : "CHECKPOINT_PROMPT",
              },
              {
                title: "Model",
                dataIndex: "model",
                width: 180,
                ellipsis: true,
              },
              {
                title: "Status",
                dataIndex: "status",
                width: 110,
                render: (value: PromptTestRecord["status"]) => (
                  <Tag color={value === "success" ? "green" : value === "failed" ? "red" : "blue"}>{value}</Tag>
                ),
              },
              {
                title: "Input",
                dataIndex: "input_text",
                ellipsis: true,
              },
              {
                title: "Created By",
                dataIndex: "created_by",
                width: 140,
              },
              {
                title: "Created At",
                dataIndex: "created_at",
                width: 190,
                render: (value: string) => new Date(value).toLocaleString(),
              },
              {
                title: "Action",
                width: 96,
                render: (_, record) => (
                  <Tooltip title="View record">
                    <Button icon={<EyeOutlined />} onClick={() => setSelectedRecord(record)} />
                  </Tooltip>
                ),
              },
            ]}
          />
        </Card>
      </Space>
      <Modal
        width={960}
        title={selectedRecord ? `Prompt Test #${selectedRecord.id}` : "Prompt Test"}
        open={Boolean(selectedRecord)}
        onCancel={() => setSelectedRecord(null)}
        footer={null}
      >
        {selectedRecord && (
          <Space direction="vertical" size={16} className="prompt-test-results">
            <Typography.Text strong>Output</Typography.Text>
            <Typography.Text className="model-output">
              {selectedRecord.error_message || formatOutput(selectedRecord.output)}
            </Typography.Text>
            <Typography.Text strong>Rendered Prompt</Typography.Text>
            <Typography.Text className="model-output">{selectedRecord.rendered_prompt}</Typography.Text>
            <Typography.Text strong>Input Text</Typography.Text>
            <Typography.Text className="model-output">{selectedRecord.input_text}</Typography.Text>
          </Space>
        )}
      </Modal>
    </div>
  );
};
