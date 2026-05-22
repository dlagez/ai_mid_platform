import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGetIdentity } from "@refinedev/core";
import { Button, Card, DatePicker, Form, Input, Modal, Select, Space, Table, Tag, message } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { CheckCircleOutlined, EditOutlined, ImportOutlined, ReloadOutlined, StopOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  importStandardFromDocument,
  listStandards,
  updateStandard,
  type ImportStandardRequest,
  type StandardDocument,
  type StandardDocumentPayload,
} from "../services/standardService";
import { listPPOcrPdfJobs, type PPOcrPdfJob } from "../services/utilsService";

type StandardFormValues = Omit<StandardDocumentPayload, "effective_date"> & {
  effective_date?: Dayjs | null;
};

type ImportStandardFormValues = Omit<ImportStandardRequest, "effective_date"> & {
  effective_date?: Dayjs | null;
};

export const StandardsListPage = () => {
  const navigate = useNavigate();
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [standards, setStandards] = useState<StandardDocument[]>([]);
  const [parseJobs, setParseJobs] = useState<PPOcrPdfJob[]>([]);
  const [editing, setEditing] = useState<StandardDocument | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [loading, setLoading] = useState({ list: false, save: false, import: false, status: false, parseJobs: false });
  const [editForm] = Form.useForm<StandardFormValues>();
  const [importForm] = Form.useForm<ImportStandardFormValues>();

  const refresh = async () => {
    setLoading((current) => ({ ...current, list: true }));
    try {
      const result = await listStandards();
      setStandards(result.items);
    } catch {
      message.error("Failed to load standards.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const loadParseJobs = async () => {
    setLoading((current) => ({ ...current, parseJobs: true }));
    try {
      const jobs = await listPPOcrPdfJobs();
      setParseJobs(jobs.filter((job) => job.parse_result_id));
    } catch {
      message.error("Failed to load parsed PDF jobs.");
    } finally {
      setLoading((current) => ({ ...current, parseJobs: false }));
    }
  };

  const openImport = async () => {
    importForm.resetFields();
    setImportOpen(true);
    await loadParseJobs();
  };

  const handleParseResultSelect = (parseResultId?: number | null) => {
    if (!parseResultId) {
      return;
    }
    const selected = parseJobs.find((job) => job.parse_result_id === parseResultId);
    if (!selected) {
      return;
    }
    if (!importForm.getFieldValue("standard_name")) {
      importForm.setFieldValue("standard_name", stripExtension(selected.file_name));
    }
  };

  const openEdit = (standard: StandardDocument) => {
    setEditing(standard);
    editForm.setFieldsValue({
      standard_code: standard.standard_code,
      standard_name: standard.standard_name,
      standard_type: standard.standard_type,
      version: standard.version,
      effective_date: standard.effective_date ? dayjs(standard.effective_date) : null,
      status: standard.status,
      description: standard.description,
    });
  };

  const saveEdit = async () => {
    if (!editing) {
      return;
    }
    const values = await editForm.validateFields();
    setLoading((current) => ({ ...current, save: true }));
    try {
      await updateStandard(editing.id, normalizeStandardPayload(values));
      message.success("Standard saved.");
      setEditing(null);
      await refresh();
    } catch {
      message.error("Failed to save standard.");
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  const submitImport = async () => {
    const values = await importForm.validateFields();
    setLoading((current) => ({ ...current, import: true }));
    try {
      const result = await importStandardFromDocument({
        ...values,
        effective_date: values.effective_date ? values.effective_date.format("YYYY-MM-DD") : null,
      });
      message.success(`Imported standard ${result.standard_id}, ${result.clause_count} clauses generated.`);
      setImportOpen(false);
      importForm.resetFields();
      await refresh();
    } catch {
      message.error("Failed to import standard.");
    } finally {
      setLoading((current) => ({ ...current, import: false }));
    }
  };

  const changeStatus = async (standard: StandardDocument, status: "active" | "disabled") => {
    setLoading((current) => ({ ...current, status: true }));
    try {
      await updateStandard(standard.id, { status });
      message.success("Standard status updated.");
      await refresh();
    } catch {
      message.error("Failed to update standard status.");
    } finally {
      setLoading((current) => ({ ...current, status: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Standards Library</h1>
        <Space>
          <Button icon={<ReloadOutlined />} loading={loading.list} onClick={() => void refresh()}>
            Refresh
          </Button>
          {isAdmin ? (
            <Button type="primary" icon={<ImportOutlined />} onClick={() => void openImport()}>
              Import From Parsed Document
            </Button>
          ) : null}
        </Space>
      </div>

      <Card>
        <Table<StandardDocument>
          rowKey="id"
          loading={loading.list}
          dataSource={standards}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: "Code", dataIndex: "standard_code", width: 160 },
            { title: "Name", dataIndex: "standard_name", ellipsis: true },
            { title: "Type", dataIndex: "standard_type", width: 120 },
            { title: "Version", dataIndex: "version", width: 100 },
            { title: "Effective Date", dataIndex: "effective_date", width: 140 },
            {
              title: "Status",
              dataIndex: "status",
              width: 110,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Created At",
              dataIndex: "created_at",
              width: 180,
              render: (value: string) => formatDateTime(value),
            },
            {
              title: "Actions",
              width: 260,
              render: (_, record) => (
                <Space size={6} wrap>
                  <Button size="small" onClick={() => navigate(`/standards/${record.id}/clauses`)}>
                    Clauses
                  </Button>
                  {isAdmin ? (
                    <>
                      <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
                        Edit
                      </Button>
                      {record.status === "active" ? (
                        <Button
                          size="small"
                          icon={<StopOutlined />}
                          loading={loading.status}
                          onClick={() => void changeStatus(record, "disabled")}
                        >
                          Disable
                        </Button>
                      ) : (
                        <Button
                          size="small"
                          icon={<CheckCircleOutlined />}
                          loading={loading.status}
                          onClick={() => void changeStatus(record, "active")}
                        >
                          Activate
                        </Button>
                      )}
                    </>
                  ) : null}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Edit Standard"
        open={Boolean(editing)}
        confirmLoading={loading.save}
        onOk={() => void saveEdit()}
        onCancel={() => setEditing(null)}
      >
        <StandardForm form={editForm} />
      </Modal>

      <Modal
        title="Import Standard From Parsed Document"
        open={importOpen}
        confirmLoading={loading.import}
        onOk={() => void submitImport()}
        onCancel={() => setImportOpen(false)}
      >
        <Form form={importForm} layout="vertical" requiredMark={false}>
          <Form.Item
            name="document_id"
            label="Parse Result ID"
            tooltip="Optional. Select a PPOCR parse result to import clauses; leave empty to create a standard record only."
          >
            <Select
              allowClear
              showSearch
              loading={loading.parseJobs}
              placeholder="Select parse result"
              optionFilterProp="label"
              onChange={handleParseResultSelect}
              options={parseJobs.map((job) => ({
                value: job.parse_result_id,
                label: `${job.parse_result_id} - ${job.file_name}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="standard_code" label="Standard Code">
            <Input />
          </Form.Item>
          <Form.Item name="standard_name" label="Standard Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="standard_type" label="Type">
            <Select options={standardTypeOptions} allowClear />
          </Form.Item>
          <Form.Item name="version" label="Version">
            <Input />
          </Form.Item>
          <Form.Item name="effective_date" label="Effective Date">
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const StandardForm = ({ form }: { form: ReturnType<typeof Form.useForm<StandardFormValues>>[0] }) => (
  <Form form={form} layout="vertical" requiredMark={false}>
    <Form.Item name="standard_code" label="Standard Code">
      <Input />
    </Form.Item>
    <Form.Item name="standard_name" label="Standard Name" rules={[{ required: true }]}>
      <Input />
    </Form.Item>
    <Form.Item name="standard_type" label="Type">
      <Select options={standardTypeOptions} allowClear />
    </Form.Item>
    <Form.Item name="version" label="Version">
      <Input />
    </Form.Item>
    <Form.Item name="effective_date" label="Effective Date">
      <DatePicker style={{ width: "100%" }} />
    </Form.Item>
    <Form.Item name="status" label="Status">
      <Select
        options={[
          { value: "draft", label: "draft" },
          { value: "active", label: "active" },
          { value: "disabled", label: "disabled" },
          { value: "archived", label: "archived" },
        ]}
      />
    </Form.Item>
    <Form.Item name="description" label="Description">
      <Input.TextArea rows={4} />
    </Form.Item>
  </Form>
);

const standardTypeOptions = [
  { value: "national", label: "national" },
  { value: "industry", label: "industry" },
  { value: "local", label: "local" },
  { value: "enterprise", label: "enterprise" },
  { value: "other", label: "other" },
];

const normalizeStandardPayload = (values: StandardFormValues): StandardDocumentPayload => ({
  ...values,
  effective_date: values.effective_date ? values.effective_date.format("YYYY-MM-DD") : null,
});

const StatusTag = ({ status }: { status: string }) => {
  const color = status === "active" ? "green" : status === "disabled" ? "red" : status === "archived" ? "default" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDateTime = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const stripExtension = (fileName: string) => fileName.replace(/\.[^/.]+$/, "");
