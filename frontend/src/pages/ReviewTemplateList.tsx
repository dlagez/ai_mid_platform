import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGetIdentity } from "@refinedev/core";
import { Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, message } from "antd";
import {
  CheckCircleOutlined,
  DeleteOutlined,
  ImportOutlined,
  ReloadOutlined,
  StopOutlined,
} from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import { listDocuments, type DocumentRecord } from "../services/documentService";
import {
  activateReviewTemplate,
  archiveReviewTemplate,
  disableReviewTemplate,
  importReviewTemplateFromDocument,
  listReviewTemplates,
  type ImportTemplateRequest,
  type ReviewTemplate,
} from "../services/reviewTemplateService";

export const ReviewTemplateListPage = () => {
  const navigate = useNavigate();
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [templates, setTemplates] = useState<ReviewTemplate[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [loading, setLoading] = useState({ list: false, import: false, status: false, delete: false, documents: false });
  const [form] = Form.useForm<ImportTemplateRequest>();

  const refresh = async () => {
    setLoading((current) => ({ ...current, list: true }));
    try {
      const result = await listReviewTemplates();
      setTemplates(result.items);
    } catch {
      message.error("Failed to load Templates Rules.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  const loadDocuments = async () => {
    setLoading((current) => ({ ...current, documents: true }));
    try {
      setDocuments(await listDocuments({ document_type: "template" }));
    } catch {
      message.error("Failed to load parsed documents.");
    } finally {
      setLoading((current) => ({ ...current, documents: false }));
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const openImport = async () => {
    form.resetFields();
    setImportOpen(true);
    await loadDocuments();
  };

  const handleDocumentSelect = (documentId: number) => {
    const document = documents.find((item) => item.id === documentId);
    if (!document) {
      return;
    }
    form.setFieldsValue({
      name: document.file_name,
      code: generateTemplateCode(document.id),
    });
  };

  const submitImport = async () => {
    try {
      const values = await form.validateFields();
      setLoading((current) => ({ ...current, import: true }));
      const result = await importReviewTemplateFromDocument(values);
      message.success(`Imported template ${result.template_id}, ${result.section_rule_count} rules generated.`);
      setImportOpen(false);
      await refresh();
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setLoading((current) => ({ ...current, import: false }));
    }
  };

  const changeStatus = async (record: ReviewTemplate, nextStatus: "active" | "disabled") => {
    setLoading((current) => ({ ...current, status: true }));
    try {
      if (nextStatus === "active") {
        await activateReviewTemplate(record.id);
      } else {
        await disableReviewTemplate(record.id);
      }
      message.success("Template status updated.");
      await refresh();
    } catch {
      message.error("Failed to update template status.");
    } finally {
      setLoading((current) => ({ ...current, status: false }));
    }
  };

  const deleteTemplate = async (record: ReviewTemplate) => {
    setLoading((current) => ({ ...current, delete: true }));
    try {
      await archiveReviewTemplate(record.id);
      message.success("Template deleted.");
      await refresh();
    } catch {
      message.error("Failed to delete template.");
    } finally {
      setLoading((current) => ({ ...current, delete: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Templates Rules</h1>
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
        <Table<ReviewTemplate>
          rowKey="id"
          loading={loading.list}
          dataSource={templates}
          onRow={(record) => ({
            onClick: () => {
              setSelectedTemplateId(record.id);
              navigate(`/review-templates/${record.id}`);
            },
            className: `document-row${selectedTemplateId === record.id ? " document-row-selected" : ""}`,
          })}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: "Name", dataIndex: "name", ellipsis: true },
            { title: "Code", dataIndex: "code", width: 150 },
            { title: "Work Type", dataIndex: "work_type", width: 140 },
            { title: "Version", dataIndex: "version", width: 100 },
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
              width: 240,
              render: (_, record) => (
                <Space size={6} wrap onClick={(e) => e.stopPropagation()}>
                  <Button size="small" onClick={() => navigate(`/review-templates/${record.id}/section-rules`)}>
                    Section Rules
                  </Button>
                  {isAdmin ? (
                    <>
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
                      <Popconfirm
                        title="Delete this template?"
                        description="The template will be archived and hidden from the list."
                        okText="Delete"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => void deleteTemplate(record)}
                      >
                        <Button size="small" danger icon={<DeleteOutlined />} loading={loading.delete}>
                          Delete
                        </Button>
                      </Popconfirm>
                    </>
                  ) : null}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Import Template From Parsed Document"
        open={importOpen}
        confirmLoading={loading.import}
        onOk={() => void submitImport()}
        onCancel={() => setImportOpen(false)}
      >
        <Form form={form} layout="vertical" requiredMark={false}>
          <Form.Item name="document_id" label="Parsed Template Document" rules={[{ required: true }]}>
            <Select
              showSearch
              loading={loading.documents}
              placeholder="Select document"
              optionFilterProp="label"
              onChange={handleDocumentSelect}
              options={documents.map((document) => ({
                value: document.id,
                label: `${document.id} - ${document.file_name}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="Code">
            <Input placeholder="Auto generated after selecting a document" />
          </Form.Item>
          <Form.Item
            name="work_type"
            label="Work Type (工程类型)"
            tooltip="用于后续按工程类型匹配模板和审核规则，例如：模板工程、脚手架工程、基坑工程。"
          >
            <Input placeholder="例如：模板工程" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const StatusTag = ({ status }: { status: string }) => {
  const color = status === "active" ? "green" : status === "disabled" ? "red" : status === "archived" ? "default" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDateTime = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const generateTemplateCode = (documentId: number) => {
  const now = new Date();
  const timestamp = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ].join("");
  return `TPL-${documentId}-${timestamp}`;
};
