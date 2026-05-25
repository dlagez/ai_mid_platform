import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message } from "antd";
import type { TablePaginationConfig } from "antd";
import { EyeOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { listDocuments, type DocumentRecord } from "../services/documentService";
import { listReviewTemplates, type ReviewTemplate } from "../services/reviewTemplateService";
import {
  createReviewTask,
  listReviewTasks,
  type ReviewTask,
  type ReviewTaskCreate,
  type ReviewTaskListQuery,
} from "../services/reviewTaskService";

type TaskFilterValues = {
  status?: string;
  plan_document_id?: number;
};

export const ReviewTasksPage = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [templates, setTemplates] = useState<ReviewTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<ReviewTaskListQuery>({ page: 1, page_size: 20 });
  const [createOpen, setCreateOpen] = useState(false);
  const [loading, setLoading] = useState({ list: false, create: false, options: false });
  const [filterForm] = Form.useForm<TaskFilterValues>();
  const [createForm] = Form.useForm<ReviewTaskCreate>();

  const load = async (nextQuery = query) => {
    setLoading((current) => ({ ...current, list: true }));
    try {
      const result = await listReviewTasks(nextQuery);
      setTasks(result.items);
      setTotal(result.total);
      setQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
    } catch {
      message.error("Failed to load review tasks.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  const loadOptions = async () => {
    setLoading((current) => ({ ...current, options: true }));
    try {
      const [documentItems, templateResult] = await Promise.all([
        listDocuments({ document_type: "construction_plan" }),
        listReviewTemplates(),
      ]);
      setDocuments(documentItems);
      setTemplates(templateResult.items.filter((template) => template.status === "active"));
    } catch {
      message.error("Failed to load documents or templates.");
    } finally {
      setLoading((current) => ({ ...current, options: false }));
    }
  };

  useEffect(() => {
    void load();
    void loadOptions();
  }, []);

  const openCreate = () => {
    createForm.resetFields();
    createForm.setFieldsValue({ review_mode: "standard" });
    setCreateOpen(true);
  };

  const handleDocumentSelect = (documentId: number) => {
    const document = documents.find((item) => item.id === documentId);
    if (!document) {
      return;
    }
    if (!createForm.getFieldValue("task_name")) {
      createForm.setFieldValue("task_name", `${stripExtension(document.file_name)}审核`);
    }
  };

  const handleTemplateSelect = (templateId?: number | null) => {
    if (!templateId) {
      return;
    }
    const template = templates.find((item) => item.id === templateId);
    if (template?.work_type && !createForm.getFieldValue("work_type")) {
      createForm.setFieldValue("work_type", template.work_type);
    }
  };

  const submitCreate = async () => {
    const values = await createForm.validateFields();
    setLoading((current) => ({ ...current, create: true }));
    try {
      const task = await createReviewTask({
        ...values,
        template_id: values.template_id ?? null,
        work_type: values.work_type || null,
      });
      message.success("Review task created.");
      setCreateOpen(false);
      await load();
      navigate(`/review-tasks/${task.id}`);
    } catch {
      message.error("Failed to create review task.");
    } finally {
      setLoading((current) => ({ ...current, create: false }));
    }
  };

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

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Review Tasks</h1>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading.list} onClick={() => void load()}>
            Refresh
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Create Review Task
          </Button>
        </Space>
      </div>

      <Card>
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 170 }} options={taskStatusOptions} />
          </Form.Item>
          <Form.Item name="plan_document_id" label="Plan Document ID">
            <InputNumber min={1} style={{ width: 160 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <Table<ReviewTask>
          rowKey="id"
          loading={loading.list}
          dataSource={tasks}
          pagination={{
            current: query.page,
            pageSize: query.page_size,
            total,
            showSizeChanger: true,
          }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            { title: "Task Name", dataIndex: "task_name", ellipsis: true },
            { title: "Plan Document ID", dataIndex: "plan_document_id", width: 150 },
            { title: "Template ID", dataIndex: "template_id", width: 110, render: (value: number | null) => value ?? "-" },
            { title: "Work Type", dataIndex: "work_type", width: 130 },
            { title: "Mode", dataIndex: "review_mode", width: 110 },
            { title: "Version", dataIndex: "version", width: 90, render: (value: number) => `v${value}` },
            {
              title: "Status",
              dataIndex: "status",
              width: 140,
              render: (value: string) => <StatusTag status={value} />,
            },
            { title: "Issues", dataIndex: "total_issue_count", width: 90 },
            { title: "Critical", dataIndex: "critical_issue_count", width: 90 },
            { title: "Major", dataIndex: "major_issue_count", width: 80 },
            {
              title: "Created At",
              dataIndex: "created_at",
              width: 180,
              render: (value: string) => formatDateTime(value),
            },
            {
              title: "Actions",
              width: 100,
              render: (_, record) => (
                <Space size={6} wrap>
                  <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/review-tasks/${record.id}`)}>
                    Issues
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Create Review Task"
        open={createOpen}
        confirmLoading={loading.create}
        onOk={() => void submitCreate()}
        onCancel={() => setCreateOpen(false)}
      >
        <Form form={createForm} layout="vertical" requiredMark={false}>
          <Form.Item name="plan_document_id" label="Construction Plan Document" rules={[{ required: true }]}>
            <Select
              showSearch
              loading={loading.options}
              placeholder="Select parsed plan document"
              optionFilterProp="label"
              onChange={handleDocumentSelect}
              options={documents.map((document) => ({
                value: document.id,
                label: `${document.id} - ${document.file_name}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="template_id" label="Review Template">
            <Select
              allowClear
              showSearch
              loading={loading.options}
              placeholder="Optional active template"
              optionFilterProp="label"
              onChange={handleTemplateSelect}
              options={templates.map((template) => ({
                value: template.id,
                label: `${template.id} - ${template.name}${template.work_type ? ` / ${template.work_type}` : ""}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="task_name" label="Task Name">
            <Input />
          </Form.Item>
          <Form.Item name="work_type" label="Work Type">
            <Input placeholder="例如：模板工程" />
          </Form.Item>
          <Form.Item name="review_mode" label="Review Mode" rules={[{ required: true }]}>
            <Select options={reviewModeOptions} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const taskStatusOptions = [
  { value: "created", label: "created" },
  { value: "running", label: "running" },
  { value: "pending_confirm", label: "pending_confirm" },
  { value: "completed", label: "completed" },
  { value: "failed", label: "failed" },
  { value: "cancelled", label: "cancelled" },
];

const reviewModeOptions = [
  { value: "quick", label: "quick" },
  { value: "standard", label: "standard" },
  { value: "deep", label: "deep" },
];

const StatusTag = ({ status }: { status: string }) => {
  const color =
    status === "completed" ? "green" : status === "failed" ? "red" : status === "running" ? "processing" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDateTime = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const stripExtension = (fileName: string) => fileName.replace(/\.[^/.]+$/, "");
