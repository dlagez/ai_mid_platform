import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Checkbox,
  Col,
  Divider,
  Form,
  Input,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import type { Key } from "react";
import {
  CloudUploadOutlined,
  CommentOutlined,
  FileSearchOutlined,
  FolderOpenOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  SearchOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { PdfPreviewModal } from "../components/PdfPreviewModal";
import { fetchPdfPreviewUrl } from "../services/filePreviewService";
import {
  addKnowledgePath,
  chatKnowledge,
  clearKnowledgeSession,
  exitKnowledgeSession,
  getKnowledgeStatus,
  helpKnowledge,
  lintKnowledge,
  listKnowledgeFiles,
  listKnowledge,
  queryKnowledge,
  saveKnowledgeTranscript,
  uploadKnowledgeFile,
  type KnowledgeAddResult,
  type KnowledgeChatResult,
  type KnowledgeCommand,
  type KnowledgeList,
  type KnowledgeQueryResult,
  type KnowledgeRawFile,
  type KnowledgeRawFiles,
  type KnowledgeStatus,
} from "../services/knowledgeService";

type QueryForm = {
  question: string;
  save: boolean;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const getErrorStatus = (error: unknown) => {
  if (typeof error === "object" && error !== null && "response" in error) {
    return (error as { response?: { status?: number } }).response?.status;
  }
  return undefined;
};

const showAddResultMessage = (result: KnowledgeAddResult) => {
  if (result.added.length > 0) {
    message.success(`Added ${result.added.length} document(s).`);
    return;
  }
  if (result.skipped.length > 0) {
    message.warning(result.skipped[0]);
    return;
  }
  message.info("No document changes.");
};

export const OpenKBPage = () => {
  const [kbName, setKbName] = useState("default");
  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [knowledgeList, setKnowledgeList] = useState<KnowledgeList | null>(null);
  const [addResult, setAddResult] = useState<KnowledgeAddResult | null>(null);
  const [queryResult, setQueryResult] = useState<KnowledgeQueryResult | null>(null);
  const [chatSessionId, setChatSessionId] = useState<string | undefined>();
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [commands, setCommands] = useState<KnowledgeCommand[]>([]);
  const [commandOutput, setCommandOutput] = useState<string>("Command output will appear here.");
  const [rawFiles, setRawFiles] = useState<KnowledgeRawFiles | null>(null);
  const [selectedRawFileKeys, setSelectedRawFileKeys] = useState<Key[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [pdfPreview, setPdfPreview] = useState({ open: false, title: "", url: "" });
  const [loading, setLoading] = useState({
    status: false,
    add: false,
    query: false,
    chat: false,
    command: false,
  });

  const activeKbName = kbName.trim() || "default";

  const metrics = useMemo(
    () => ({
      documents: status?.total_indexed ?? 0,
      summaries: status?.directories.summaries ?? 0,
      concepts: status?.directories.concepts ?? 0,
      raw: status?.directories.raw ?? 0,
    }),
    [status],
  );

  const refreshKnowledge = async () => {
    setLoading((current) => ({ ...current, status: true }));
    try {
      const [nextStatus, nextList, nextFiles] = await Promise.all([
        getKnowledgeStatus(activeKbName),
        listKnowledge(activeKbName),
        listKnowledgeFiles(activeKbName),
      ]);
      setStatus(nextStatus);
      setKnowledgeList(nextList);
      setRawFiles(nextFiles);
      setSelectedRawFileKeys((current) =>
        current.filter((key) => nextFiles.files.some((file) => file.path === key)),
      );
    } catch (error) {
      message.error("Unable to load OpenKB status.");
    } finally {
      setLoading((current) => ({ ...current, status: false }));
    }
  };

  useEffect(() => {
    void refreshKnowledge();
    void handleHelp();
  }, []);

  const handleAddSelected = async () => {
    if (selectedRawFileKeys.length === 0) {
      message.warning("Select one or more raw files first.");
      return;
    }
    setLoading((current) => ({ ...current, add: true }));
    try {
      const combined: KnowledgeAddResult = { kb_name: activeKbName, added: [], skipped: [] };
      for (const path of selectedRawFileKeys) {
        const result = await addKnowledgePath({ kbName: activeKbName, path: String(path) });
        combined.added.push(...result.added);
        combined.skipped.push(...result.skipped);
      }
      setAddResult(combined);
      showAddResultMessage(combined);
      await refreshKnowledge();
    } catch (error) {
      message.error(getErrorStatus(error) === 401 ? "Session expired. Login again." : "OpenKB add selected files failed.");
    } finally {
      setLoading((current) => ({ ...current, add: false }));
    }
  };

  const handleUploadFile = async () => {
    const originFile = fileList[0]?.originFileObj;
    if (!originFile) {
      message.warning("Select a file first.");
      return;
    }
    setLoading((current) => ({ ...current, add: true }));
    try {
      const result = await uploadKnowledgeFile({ kbName: activeKbName, file: originFile });
      message.success(`Uploaded ${result.filename}.`);
      setFileList([]);
      await refreshKnowledge();
    } catch (error) {
      message.error(getErrorStatus(error) === 401 ? "Session expired. Login again." : "OpenKB upload failed.");
    } finally {
      setLoading((current) => ({ ...current, add: false }));
    }
  };

  const handlePreviewRawPdf = async (file: KnowledgeRawFile) => {
    try {
      const url = await fetchPdfPreviewUrl("/knowledge/files/preview", {
        kb_name: activeKbName,
        relative_path: file.relative_path,
      });
      setPdfPreview({ open: true, title: file.name, url });
    } catch {
      message.error("PDF preview failed.");
    }
  };

  const handleQuery = async (values: QueryForm) => {
    setLoading((current) => ({ ...current, query: true }));
    try {
      const result = await queryKnowledge({
        kbName: activeKbName,
        question: values.question,
        save: values.save,
      });
      setQueryResult(result);
    } catch (error) {
      message.error("OpenKB query failed.");
    } finally {
      setLoading((current) => ({ ...current, query: false }));
    }
  };

  const handleChat = async (values: { message: string }) => {
    setLoading((current) => ({ ...current, chat: true }));
    const userMessage: ChatMessage = { role: "user", content: values.message };
    setChatMessages((current) => [...current, userMessage]);
    try {
      const result: KnowledgeChatResult = await chatKnowledge({
        kbName: activeKbName,
        message: values.message,
        sessionId: chatSessionId,
      });
      setChatSessionId(result.session_id);
      setChatMessages((current) => [...current, { role: "assistant", content: result.answer }]);
    } catch (error) {
      message.error("OpenKB chat failed.");
    } finally {
      setLoading((current) => ({ ...current, chat: false }));
    }
  };

  const runCommand = async (action: () => Promise<unknown>, successMessage?: string) => {
    setLoading((current) => ({ ...current, command: true }));
    try {
      const result = await action();
      setCommandOutput(JSON.stringify(result, null, 2));
      if (successMessage) {
        message.success(successMessage);
      }
      return result;
    } catch (error) {
      message.error(getErrorStatus(error) === 401 ? "Session expired. Login again." : "OpenKB command failed.");
      return null;
    } finally {
      setLoading((current) => ({ ...current, command: false }));
    }
  };

  const handleHelp = async () => {
    const result = await runCommand(() => helpKnowledge());
    if (result && typeof result === "object" && "commands" in result) {
      setCommands((result as { commands: KnowledgeCommand[] }).commands);
    }
  };

  const handleCommandStatus = async () => {
    const result = await runCommand(() => getKnowledgeStatus(activeKbName));
    if (result) {
      setStatus(result as KnowledgeStatus);
    }
  };

  const handleCommandList = async () => {
    const result = await runCommand(() => listKnowledge(activeKbName));
    if (result) {
      setKnowledgeList(result as KnowledgeList);
    }
  };

  const handleSaveTranscript = async () => {
    if (!chatSessionId) {
      message.warning("Start a chat session before saving.");
      return;
    }
    await runCommand(
      () => saveKnowledgeTranscript({ kbName: activeKbName, sessionId: chatSessionId }),
      "Transcript saved.",
    );
  };

  const handleClearSession = async () => {
    const result = await runCommand(
      () => clearKnowledgeSession({ kbName: activeKbName, previousSessionId: chatSessionId }),
      "Started a fresh session.",
    );
    if (result && typeof result === "object" && "session_id" in result) {
      setChatSessionId((result as { session_id: string }).session_id);
      setChatMessages([]);
    }
  };

  const handleLint = async () => {
    await runCommand(() => lintKnowledge({ kbName: activeKbName }), "Lint finished.");
    await refreshKnowledge();
  };

  const handleExitSession = async () => {
    await runCommand(
      () => exitKnowledgeSession({ kbName: activeKbName, sessionId: chatSessionId }),
      "Exited chat session.",
    );
    setChatSessionId(undefined);
    setChatMessages([]);
  };

  type CommandRow = {
    command: string;
    description: string;
    action: () => void | Promise<void>;
    icon?: React.ReactNode;
    loading?: boolean;
    danger?: boolean;
  };

  const commandRows: CommandRow[] = [
    {
      command: "/help",
      description: "List available commands",
      action: handleHelp,
      icon: <InfoCircleOutlined />,
    },
    {
      command: "/status",
      description: "Show knowledge base status",
      action: handleCommandStatus,
    },
    {
      command: "/list",
      description: "List all documents",
      action: handleCommandList,
    },
    {
      command: "/add <path>",
      description: "Use the Add Documents panel",
      action: () => setCommandOutput("Use the Add Documents panel on the left for /add <path> or upload."),
      icon: <FolderOpenOutlined />,
      loading: loading.add,
    },
    {
      command: "/save [name]",
      description: "Export current chat transcript",
      action: handleSaveTranscript,
      icon: <SaveOutlined />,
    },
    {
      command: "/clear",
      description: "Start a fresh session",
      action: handleClearSession,
      icon: <CommentOutlined />,
    },
    {
      command: "/lint",
      description: "Run knowledge base lint",
      action: handleLint,
    },
    {
      command: "/exit",
      description: "Exit current chat session",
      action: handleExitSession,
      danger: true,
    },
  ];

  return (
    <div className="page">
      <div className="page-heading">
        <h1>OpenKB</h1>
        <Space wrap>
          <Input
            prefix={<FolderOpenOutlined />}
            value={kbName}
            onChange={(event) => setKbName(event.target.value)}
            onPressEnter={() => void refreshKnowledge()}
            placeholder="KB name"
            style={{ width: 220 }}
          />
          <Button icon={<ReloadOutlined />} loading={loading.status} onClick={() => void refreshKnowledge()}>
            Refresh
          </Button>
        </Space>
      </div>

      <div className="metric-grid">
        <Card className="metric-card">
          <Statistic title="Indexed Docs" value={metrics.documents} prefix={<FileSearchOutlined />} />
        </Card>
        <Card className="metric-card">
          <Statistic title="Summaries" value={metrics.summaries} />
        </Card>
        <Card className="metric-card">
          <Statistic title="Concepts" value={metrics.concepts} />
        </Card>
        <Card className="metric-card">
          <Statistic title="Raw Files" value={metrics.raw} />
        </Card>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card title="Add Documents">
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Upload
                  beforeUpload={() => false}
                  fileList={fileList}
                  maxCount={1}
                  onChange={({ fileList: nextFileList }) => setFileList(nextFileList)}
                >
                  <Button icon={<CloudUploadOutlined />}>Select File</Button>
                </Upload>
                <Button loading={loading.add} onClick={() => void handleUploadFile()} icon={<CloudUploadOutlined />}>
                  Upload To Raw
                </Button>
              </Space>

              <Divider />

              <Table<KnowledgeRawFile>
                rowKey="path"
                size="small"
                dataSource={rawFiles?.files ?? []}
                pagination={{ pageSize: 5 }}
                rowSelection={{
                  selectedRowKeys: selectedRawFileKeys,
                  onChange: setSelectedRawFileKeys,
                  getCheckboxProps: (record) => ({
                    disabled: !record.supported,
                  }),
                }}
                columns={[
                  {
                    title: "Raw File",
                    dataIndex: "name",
                    ellipsis: true,
                    render: (value: string, row) =>
                      isPdf(value) ? (
                        <Button
                          type="link"
                          size="small"
                          className="table-link-button"
                          onClick={() => void handlePreviewRawPdf(row)}
                        >
                          {value}
                        </Button>
                      ) : (
                        value
                      ),
                  },
                  {
                    title: "State",
                    width: 100,
                    render: (_, row) => (
                      <Space size={4} wrap>
                        {!row.supported ? <Tag color="red">Unsupported</Tag> : null}
                        {row.indexed ? <Tag color="green">Indexed</Tag> : <Tag>Raw</Tag>}
                      </Space>
                    ),
                  },
                ]}
              />
              <Button
                type="primary"
                loading={loading.add}
                disabled={selectedRawFileKeys.length === 0}
                onClick={() => void handleAddSelected()}
                icon={<FolderOpenOutlined />}
              >
                Add Selected
              </Button>

              {addResult ? (
                <div className="openkb-result-block">
                  <Typography.Text strong>Last add result</Typography.Text>
                  <Typography.Paragraph className="openkb-output">
                    {JSON.stringify(addResult, null, 2)}
                  </Typography.Paragraph>
                </div>
              ) : null}
            </Card>

            <Card title="Knowledge List">
              <Table
                rowKey="hash"
                size="small"
                dataSource={knowledgeList?.documents ?? []}
                pagination={{ pageSize: 6 }}
                columns={[
                  { title: "Name", dataIndex: "name", ellipsis: true },
                  {
                    title: "Type",
                    dataIndex: "type",
                    width: 110,
                    render: (type) => <Tag>{type}</Tag>,
                  },
                ]}
              />
              <Divider />
              <Typography.Text type="secondary">
                {knowledgeList?.summaries.length ?? 0} summaries, {knowledgeList?.concepts.length ?? 0} concepts,{" "}
                {knowledgeList?.reports.length ?? 0} reports
              </Typography.Text>
            </Card>
          </Space>
        </Col>

        <Col xs={24} xl={14}>
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card title="Commands">
              <div className="openkb-command-panel">
                <Table
                  rowKey="command"
                  size="small"
                  pagination={false}
                  dataSource={commandRows}
                  columns={[
                    {
                      title: "Command",
                      dataIndex: "command",
                      width: 150,
                      render: (command: string) => <Typography.Text code>{command}</Typography.Text>,
                    },
                    {
                      title: "Purpose",
                      dataIndex: "description",
                      ellipsis: true,
                    },
                    {
                      title: "",
                      width: 96,
                      render: (_, row) => (
                        <Button
                          size="small"
                          danger={row.danger}
                          icon={row.icon}
                          loading={row.loading ?? loading.command}
                          onClick={() => void row.action()}
                        >
                          Run
                        </Button>
                      ),
                    },
                  ]}
                />
                <div className="openkb-command-output">
                  <Typography.Text strong>Output</Typography.Text>
                  <Typography.Paragraph className="openkb-output">{commandOutput}</Typography.Paragraph>
                </div>
              </div>
            </Card>

            <Card title="Query">
              <Form<QueryForm>
                layout="vertical"
                onFinish={handleQuery}
                initialValues={{ save: false }}
              >
                <Form.Item name="question" label="Question" rules={[{ required: true }]}>
                  <Input.TextArea rows={5} placeholder="Ask a one-off question against this knowledge base." />
                </Form.Item>
                <Space wrap>
                  <Form.Item name="save" valuePropName="checked" noStyle>
                    <Checkbox>Save exploration</Checkbox>
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={loading.query} icon={<SearchOutlined />}>
                    Query
                  </Button>
                </Space>
              </Form>
              <Typography.Paragraph className="openkb-output">
                {queryResult?.answer || "Query answer will appear here."}
              </Typography.Paragraph>
              {queryResult?.saved_path ? <Tag color="blue">{queryResult.saved_path}</Tag> : null}
            </Card>

            <Card
              title="Chat"
              extra={
                chatSessionId ? (
                  <Typography.Text type="secondary">Session {chatSessionId}</Typography.Text>
                ) : null
              }
            >
              <div className="chat-panel">
                {chatMessages.length ? (
                  chatMessages.map((item, index) => (
                    <div key={`${item.role}-${index}`} className={`chat-message chat-message-${item.role}`}>
                      <Tag color={item.role === "user" ? "blue" : "green"}>
                        {item.role === "user" ? "User" : "OpenKB"}
                      </Tag>
                      <Typography.Paragraph>{item.content}</Typography.Paragraph>
                    </div>
                  ))
                ) : (
                  <Typography.Text type="secondary">Start a multi-turn OpenKB session.</Typography.Text>
                )}
              </div>
              <Form layout="vertical" onFinish={handleChat}>
                <Form.Item name="message" rules={[{ required: true }]}>
                  <Input.TextArea rows={3} placeholder="Continue the conversation." />
                </Form.Item>
                <Space wrap>
                  <Button type="primary" htmlType="submit" loading={loading.chat} icon={<SendOutlined />}>
                    Send
                  </Button>
                  <Button
                    icon={<CommentOutlined />}
                    onClick={() => {
                      setChatSessionId(undefined);
                      setChatMessages([]);
                    }}
                  >
                    New Session
                  </Button>
                </Space>
              </Form>
            </Card>
          </Space>
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

const isPdf = (fileName: string) => fileName.toLowerCase().endsWith(".pdf");
