import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useGetIdentity } from "@refinedev/core";
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Tree,
  message,
} from "antd";
import type { DataNode } from "antd/es/tree";
import { ArrowLeftOutlined, DeleteOutlined, PlusOutlined, ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  createTemplateSectionRule,
  deleteTemplateSectionRule,
  getReviewTemplate,
  listTemplateSectionRules,
  updateTemplateSectionRule,
  type TemplateSectionRule,
  type TemplateSectionRulePayload,
} from "../services/reviewTemplateService";

type EditingState =
  | { mode: "update"; rule: TemplateSectionRule }
  | { mode: "create"; parentId: number | null; level: number };

export const TemplateSectionRulesPage = () => {
  const { id } = useParams();
  const templateId = Number(id);
  const navigate = useNavigate();
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [templateName, setTemplateName] = useState("Template Section Rules");
  const [treeRules, setTreeRules] = useState<TemplateSectionRule[]>([]);
  const [flatRules, setFlatRules] = useState<TemplateSectionRule[]>([]);
  const [editing, setEditing] = useState<EditingState | null>(null);
  const [loading, setLoading] = useState({ rules: false, save: false, delete: false });
  const [form] = Form.useForm<TemplateSectionRulePayload>();

  const load = async () => {
    if (!templateId) {
      return;
    }
    setLoading((current) => ({ ...current, rules: true }));
    try {
      const [template, result] = await Promise.all([getReviewTemplate(templateId), listTemplateSectionRules(templateId)]);
      setTemplateName(template.name);
      setTreeRules(result.items);
      setFlatRules(result.flat_items);
      const first = result.flat_items[0] ?? null;
      if (first) {
        selectRule(first);
      } else {
        startCreate(null, 1);
      }
    } catch {
      message.error("Failed to load template section rules.");
    } finally {
      setLoading((current) => ({ ...current, rules: false }));
    }
  };

  useEffect(() => {
    void load();
  }, [templateId]);

  const selectRule = (rule: TemplateSectionRule) => {
    setEditing({ mode: "update", rule });
    form.setFieldsValue(toFormValues(rule));
  };

  const startCreate = (parentId: number | null, level: number) => {
    setEditing({ mode: "create", parentId, level });
    form.setFieldsValue({
      parent_id: parentId,
      level,
      order_no: flatRules.length + 1,
      standard_title: "",
      required: true,
      aliases: [],
      required_points: [],
      min_word_count: 0,
      risk_level: "major",
      match_strategy: "title_semantic",
      enabled: true,
    });
  };

  const save = async () => {
    if (!isAdmin || !editing) {
      return;
    }
    const values = await form.validateFields();
    setLoading((current) => ({ ...current, save: true }));
    try {
      if (editing.mode === "create") {
        await createTemplateSectionRule(templateId, {
          ...values,
          parent_id: editing.parentId,
          level: editing.level,
        });
      } else {
        await updateTemplateSectionRule(editing.rule.id, values);
      }
      message.success("Section rule saved.");
      await load();
    } catch {
      message.error("Failed to save section rule.");
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  const remove = async () => {
    if (!isAdmin || editing?.mode !== "update") {
      return;
    }
    setLoading((current) => ({ ...current, delete: true }));
    try {
      await deleteTemplateSectionRule(editing.rule.id);
      message.success("Section rule disabled.");
      await load();
    } catch {
      message.error("Failed to delete section rule.");
    } finally {
      setLoading((current) => ({ ...current, delete: false }));
    }
  };

  const selectedKey = editing?.mode === "update" ? [String(editing.rule.id)] : [];
  const selectedParent = editing?.mode === "update" ? editing.rule : null;

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{templateName}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/review-templates")}>
            Back
          </Button>
          <Button icon={<ReloadOutlined />} loading={loading.rules} onClick={() => void load()}>
            Reload
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card
            title="Section Rule Tree"
            extra={
              isAdmin ? (
                <Button size="small" icon={<PlusOutlined />} onClick={() => startCreate(null, 1)}>
                  Add Root
                </Button>
              ) : null
            }
          >
            {treeRules.length ? (
              <div className="plan-section-tree">
                <Tree
                  blockNode
                  defaultExpandAll
                  selectedKeys={selectedKey}
                  treeData={toTreeData(treeRules)}
                  onSelect={(keys) => {
                    const key = keys[0];
                    const rule = key ? flatRules.find((item) => item.id === Number(key)) : null;
                    if (rule) {
                      selectRule(rule);
                    }
                  }}
                />
              </div>
            ) : (
              <Empty description="No section rules" />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            title={editing?.mode === "create" ? "New Section Rule" : "Section Rule Detail"}
            extra={
              isAdmin ? (
                <Space>
                  {selectedParent ? (
                    <Button size="small" icon={<PlusOutlined />} onClick={() => startCreate(selectedParent.id, selectedParent.level + 1)}>
                      Add Child
                    </Button>
                  ) : null}
                  {editing?.mode === "update" ? (
                    <Popconfirm title="Disable this section rule?" onConfirm={() => void remove()}>
                      <Button size="small" danger icon={<DeleteOutlined />} loading={loading.delete}>
                        Delete
                      </Button>
                    </Popconfirm>
                  ) : null}
                  <Button size="small" type="primary" icon={<SaveOutlined />} loading={loading.save} onClick={() => void save()}>
                    Save
                  </Button>
                </Space>
              ) : null
            }
          >
            {editing ? (
              <Form form={form} layout="vertical" disabled={!isAdmin} requiredMark={false}>
                <Row gutter={12}>
                  <Col xs={24} md={16}>
                    <Form.Item name="standard_title" label="Standard Title" rules={[{ required: true }]}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={12} md={4}>
                    <Form.Item name="level" label="Level" rules={[{ required: true }]}>
                      <InputNumber min={1} max={10} style={{ width: "100%" }} disabled={editing.mode === "create" || !isAdmin} />
                    </Form.Item>
                  </Col>
                  <Col xs={12} md={4}>
                    <Form.Item name="order_no" label="Order">
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={12}>
                  <Col xs={24} md={8}>
                    <Form.Item name="required" label="Required" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="enabled" label="Enabled" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="min_word_count" label="Min Word Count">
                      <InputNumber min={0} style={{ width: "100%" }} />
                    </Form.Item>
                  </Col>
                </Row>
                <Row gutter={12}>
                  <Col xs={24} md={12}>
                    <Form.Item name="risk_level" label="Risk Level">
                      <Select
                        options={[
                          { value: "critical", label: "critical" },
                          { value: "major", label: "major" },
                          { value: "minor", label: "minor" },
                        ]}
                      />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="match_strategy" label="Match Strategy">
                      <Select
                        options={[
                          { value: "title_semantic", label: "title_semantic" },
                          { value: "title_exact", label: "title_exact" },
                          { value: "keyword", label: "keyword" },
                          { value: "semantic", label: "semantic" },
                        ]}
                      />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item name="aliases" label="Aliases">
                  <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
                </Form.Item>
                <Form.Item name="required_points" label="Required Points">
                  <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
                </Form.Item>
              </Form>
            ) : (
              <Empty description="Select a section rule" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

const toTreeData = (rules: TemplateSectionRule[]): DataNode[] =>
  rules.map((rule) => ({
    key: String(rule.id),
    title: (
      <Space size={6}>
        <span>{rule.standard_title}</span>
        {!rule.enabled ? <span className="tree-muted-label">disabled</span> : null}
      </Space>
    ),
    children: toTreeData(rule.children ?? []),
  }));

const toFormValues = (rule: TemplateSectionRule): TemplateSectionRulePayload => ({
  parent_id: rule.parent_id,
  section_code: rule.section_code,
  standard_title: rule.standard_title,
  level: rule.level,
  order_no: rule.order_no,
  required: rule.required,
  aliases: rule.aliases,
  required_points: rule.required_points,
  min_word_count: rule.min_word_count,
  risk_level: rule.risk_level,
  match_strategy: rule.match_strategy,
  enabled: rule.enabled,
});
