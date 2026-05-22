import { useEffect, useState } from "react";
import type { Key } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGetIdentity } from "@refinedev/core";
import {
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import { ArrowLeftOutlined, EditOutlined, ReloadOutlined, RobotOutlined, SearchOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  generateRuleCandidates,
  getStandard,
  listStandardClauses,
  updateStandardClause,
  type StandardClause,
  type StandardClausePayload,
  type StandardClauseQuery,
} from "../services/standardService";

const { TextArea } = Input;

type ClauseFilterValues = {
  keyword?: string;
  clause_no?: string;
  is_mandatory?: boolean;
};

export const StandardClausesPage = () => {
  const { id } = useParams();
  const standardId = Number(id);
  const navigate = useNavigate();
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [standardName, setStandardName] = useState("Standard Clauses");
  const [clauses, setClauses] = useState<StandardClause[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<StandardClauseQuery>({ page: 1, page_size: 20 });
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([]);
  const [editing, setEditing] = useState<StandardClause | null>(null);
  const [useLlm, setUseLlm] = useState(true);
  const [loading, setLoading] = useState({ list: false, save: false, generate: false });
  const [filterForm] = Form.useForm<ClauseFilterValues>();
  const [editForm] = Form.useForm<StandardClausePayload>();

  const load = async (nextQuery = query) => {
    if (!standardId) {
      return;
    }
    setLoading((current) => ({ ...current, list: true }));
    try {
      const [standard, result] = await Promise.all([getStandard(standardId), listStandardClauses(standardId, nextQuery)]);
      setStandardName(standard.standard_name);
      setClauses(result.items);
      setTotal(result.total);
      setQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
    } catch {
      message.error("Failed to load standard clauses.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  useEffect(() => {
    void load();
  }, [standardId]);

  const applyFilter = async () => {
    const values = filterForm.getFieldsValue();
    await load({ ...values, page: 1, page_size: query.page_size ?? 20 });
  };

  const handleTableChange = async (pagination: TablePaginationConfig) => {
    await load({
      ...query,
      page: pagination.current ?? 1,
      page_size: pagination.pageSize ?? 20,
    });
  };

  const openEdit = (clause: StandardClause) => {
    setEditing(clause);
    editForm.setFieldsValue({
      clause_no: clause.clause_no,
      chapter_no: clause.chapter_no,
      title: clause.title,
      content: clause.content,
      level: clause.level,
      path: clause.path,
      is_mandatory: clause.is_mandatory,
      keywords: clause.keywords,
      applicable_work_types: clause.applicable_work_types,
      order_no: clause.order_no,
      embedding_id: clause.embedding_id,
    });
  };

  const saveEdit = async () => {
    if (!editing) {
      return;
    }
    const values = await editForm.validateFields();
    setLoading((current) => ({ ...current, save: true }));
    try {
      await updateStandardClause(editing.id, values);
      message.success("Clause saved.");
      setEditing(null);
      await load();
    } catch {
      message.error("Failed to save clause.");
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  const generateCandidates = async () => {
    const ids = selectedRowKeys.map((key) => Number(key));
    if (!ids.length) {
      message.warning("Select clauses first.");
      return;
    }
    setLoading((current) => ({ ...current, generate: true }));
    try {
      const result = await generateRuleCandidates(standardId, { clause_ids: ids, use_llm: useLlm });
      message.success(`Generated ${result.created_count} candidates.`);
      if (result.failed.length) {
        message.warning(`${result.failed.length} clauses failed. Check backend logs for details.`);
      }
      setSelectedRowKeys([]);
    } catch {
      message.error("Failed to generate rule candidates.");
    } finally {
      setLoading((current) => ({ ...current, generate: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{standardName}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/standards")}>
            Back
          </Button>
          <Button icon={<ReloadOutlined />} loading={loading.list} onClick={() => void load()}>
            Reload
          </Button>
        </Space>
      </div>

      <Card>
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="keyword" label="Keyword">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="clause_no" label="Clause No">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="is_mandatory" label="Mandatory">
            <Select
              allowClear
              style={{ width: 130 }}
              options={[
                { value: true, label: "Yes" },
                { value: false, label: "No" },
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <div className="table-toolbar">
          <Space wrap>
            <Checkbox checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)}>
              使用 LLM
            </Checkbox>
            <Tooltip title={getGenerateTooltip(isAdmin, selectedRowKeys.length)}>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                loading={loading.generate}
                disabled={!isAdmin || !selectedRowKeys.length}
                onClick={() => void generateCandidates()}
              >
                AI生成候选规则
              </Button>
            </Tooltip>
          </Space>
        </div>

        <Table<StandardClause>
          rowKey="id"
          loading={loading.list}
          dataSource={clauses}
          rowSelection={
            isAdmin
              ? {
                  selectedRowKeys,
                  onChange: (keys) => setSelectedRowKeys(keys),
                }
              : undefined
          }
          pagination={{
            current: query.page,
            pageSize: query.page_size,
            total,
            showSizeChanger: true,
          }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            { title: "Clause No", dataIndex: "clause_no", width: 130 },
            { title: "Title", dataIndex: "title", width: 220, ellipsis: true },
            {
              title: "Content",
              dataIndex: "content",
              ellipsis: true,
              render: (value: string) => <Typography.Text>{summarize(value)}</Typography.Text>,
            },
            {
              title: "Mandatory",
              dataIndex: "is_mandatory",
              width: 110,
              render: (value: boolean) => <Tag color={value ? "red" : "default"}>{value ? "Yes" : "No"}</Tag>,
            },
            {
              title: "Work Types",
              dataIndex: "applicable_work_types",
              width: 180,
              render: (values: string[]) => (
                <Space size={4} wrap>
                  {values?.map((value) => <Tag key={value}>{value}</Tag>)}
                </Space>
              ),
            },
            {
              title: "Actions",
              width: 90,
              render: (_, record) =>
                isAdmin ? (
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
                    Edit
                  </Button>
                ) : null,
            },
          ]}
        />
      </Card>

      <Modal
        title="Edit Clause"
        open={Boolean(editing)}
        width={760}
        confirmLoading={loading.save}
        onOk={() => void saveEdit()}
        onCancel={() => setEditing(null)}
      >
        <Form form={editForm} layout="vertical" requiredMark={false}>
          <Space align="start" style={{ width: "100%" }} className="form-space-row">
            <Form.Item name="clause_no" label="Clause No" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="chapter_no" label="Chapter No" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="level" label="Level" style={{ width: 120 }}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Form.Item name="title" label="Title">
            <Input />
          </Form.Item>
          <Form.Item name="content" label="Content" rules={[{ required: true }]}>
            <TextArea rows={8} />
          </Form.Item>
          <Form.Item name="path" label="Path">
            <Input />
          </Form.Item>
          <Form.Item name="is_mandatory" label="Mandatory Clause" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="keywords" label="Keywords">
            <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
          </Form.Item>
          <Form.Item name="applicable_work_types" label="Applicable Work Types">
            <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const summarize = (value: string) => {
  if (!value) {
    return "-";
  }
  return value.length > 140 ? `${value.slice(0, 140)}...` : value;
};

const getGenerateTooltip = (isAdmin: boolean, selectedCount: number) => {
  if (!isAdmin) {
    return "只有 admin 可以生成候选规则";
  }
  if (!selectedCount) {
    return "请先勾选需要生成规则的条文";
  }
  return `已选择 ${selectedCount} 条条文`;
};
