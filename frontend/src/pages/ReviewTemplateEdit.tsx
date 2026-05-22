import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGetIdentity } from "@refinedev/core";
import { Button, Card, Form, Input, Select, Space, Spin, message } from "antd";
import { ArrowLeftOutlined, SaveOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  getReviewTemplate,
  updateReviewTemplate,
  type ReviewTemplate,
  type ReviewTemplatePayload,
} from "../services/reviewTemplateService";

export const ReviewTemplateEditPage = () => {
  const { id } = useParams();
  const templateId = Number(id);
  const navigate = useNavigate();
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [template, setTemplate] = useState<ReviewTemplate | null>(null);
  const [loading, setLoading] = useState({ detail: false, save: false });
  const [form] = Form.useForm<ReviewTemplatePayload>();

  const load = async () => {
    if (!templateId) {
      return;
    }
    setLoading((current) => ({ ...current, detail: true }));
    try {
      const result = await getReviewTemplate(templateId);
      setTemplate(result);
      form.setFieldsValue({
        name: result.name,
        code: result.code,
        work_type: result.work_type,
        description: result.description,
        version: result.version,
        status: result.status,
      });
    } catch {
      message.error("Failed to load review template.");
    } finally {
      setLoading((current) => ({ ...current, detail: false }));
    }
  };

  useEffect(() => {
    void load();
  }, [templateId]);

  const save = async () => {
    if (!templateId || !isAdmin) {
      return;
    }
    const values = await form.validateFields();
    setLoading((current) => ({ ...current, save: true }));
    try {
      const result = await updateReviewTemplate(templateId, values);
      setTemplate(result);
      message.success("Template saved.");
    } catch {
      message.error("Failed to save template.");
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{template?.name ?? "Review Template"}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/review-templates")}>
            Back
          </Button>
          {isAdmin ? (
            <Button type="primary" icon={<SaveOutlined />} loading={loading.save} onClick={() => void save()}>
              Save
            </Button>
          ) : null}
        </Space>
      </div>

      <Card>
        <Spin spinning={loading.detail}>
          <Form form={form} layout="vertical" disabled={!isAdmin} requiredMark={false} className="narrow-form">
            <Form.Item name="name" label="Name" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="code" label="Code">
              <Input />
            </Form.Item>
            <Form.Item name="work_type" label="Work Type">
              <Input />
            </Form.Item>
            <Form.Item name="version" label="Version">
              <Input />
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
              <Input.TextArea rows={5} />
            </Form.Item>
          </Form>
        </Spin>
      </Card>
    </div>
  );
};
