import { useEffect, useState } from "react";
import { useGetIdentity } from "@refinedev/core";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import { CheckCircleOutlined, EyeOutlined, ReloadOutlined, SaveOutlined, SearchOutlined, StopOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";
import {
  approveRuleCandidate,
  listRuleCandidates,
  rejectRuleCandidate,
  updateRuleCandidate,
  type ReviewRuleCandidate,
  type ReviewRuleCandidatePayload,
  type ReviewRuleCandidateQuery,
} from "../services/reviewRuleService";

type CandidateFilterValues = {
  status?: string;
  standard_id?: number;
  rule_type?: string;
  work_type?: string;
  keyword?: string;
};

type CandidateFormValues = Omit<ReviewRuleCandidatePayload, "applicable_condition"> & {
  applicable_condition?: string;
};

export const RuleCandidatesPage = () => {
  const { data: user } = useGetIdentity<CurrentUser>();
  const isAdmin = user?.role === "admin";
  const [candidates, setCandidates] = useState<ReviewRuleCandidate[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState<ReviewRuleCandidateQuery>({ page: 1, page_size: 20 });
  const [selected, setSelected] = useState<ReviewRuleCandidate | null>(null);
  const [loading, setLoading] = useState({ list: false, save: false, approve: false, reject: false });
  const [filterForm] = Form.useForm<CandidateFilterValues>();
  const [editForm] = Form.useForm<CandidateFormValues>();

  const load = async (nextQuery = query) => {
    setLoading((current) => ({ ...current, list: true }));
    try {
      const result = await listRuleCandidates(nextQuery);
      setCandidates(result.items);
      setTotal(result.total);
      setQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
    } catch {
      message.error("Failed to load rule candidates.");
    } finally {
      setLoading((current) => ({ ...current, list: false }));
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openDetail = (candidate: ReviewRuleCandidate) => {
    setSelected(candidate);
    editForm.setFieldsValue({
      rule_name: candidate.rule_name,
      rule_type: candidate.rule_type,
      work_type: candidate.work_type,
      check_object: candidate.check_object,
      operator: candidate.operator,
      threshold_value: candidate.threshold_value,
      unit: candidate.unit,
      required_items: candidate.required_items,
      forbidden_items: candidate.forbidden_items,
      applicable_condition: JSON.stringify(candidate.applicable_condition ?? {}, null, 2),
      risk_level_suggestion: candidate.risk_level_suggestion,
      ai_confidence: candidate.ai_confidence,
      ai_reason: candidate.ai_reason,
      status: candidate.status,
    });
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

  const save = async () => {
    if (!selected || !isAdmin) {
      return;
    }
    const values = await editForm.validateFields();
    const payload = normalizeCandidatePayload(values);
    if (!payload) {
      message.error("Applicable condition must be valid JSON.");
      return;
    }
    setLoading((current) => ({ ...current, save: true }));
    try {
      const result = await updateRuleCandidate(selected.id, payload);
      setSelected(result);
      message.success("Candidate saved.");
      await load();
    } catch {
      message.error("Failed to save candidate.");
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  const approve = async (candidate: ReviewRuleCandidate) => {
    setLoading((current) => ({ ...current, approve: true }));
    try {
      await approveRuleCandidate(candidate.id);
      message.success("Candidate approved and review rule created.");
      setSelected(null);
      await load();
    } catch {
      message.error("Failed to approve candidate.");
    } finally {
      setLoading((current) => ({ ...current, approve: false }));
    }
  };

  const reject = async (candidate: ReviewRuleCandidate) => {
    setLoading((current) => ({ ...current, reject: true }));
    try {
      await rejectRuleCandidate(candidate.id);
      message.success("Candidate rejected.");
      setSelected(null);
      await load();
    } catch {
      message.error("Failed to reject candidate.");
    } finally {
      setLoading((current) => ({ ...current, reject: false }));
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Rule Candidates</h1>
        <Button icon={<ReloadOutlined />} loading={loading.list} onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      <Card>
        <Form form={filterForm} layout="inline" className="table-filter-form">
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 170 }} options={candidateStatusOptions} />
          </Form.Item>
          <Form.Item name="standard_id" label="Standard ID">
            <InputNumber min={1} style={{ width: 130 }} />
          </Form.Item>
          <Form.Item name="rule_type" label="Rule Type">
            <Select allowClear style={{ width: 190 }} options={ruleTypeOptions} />
          </Form.Item>
          <Form.Item name="work_type" label="Work Type">
            <Input allowClear />
          </Form.Item>
          <Form.Item name="keyword" label="Keyword">
            <Input allowClear />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>

        <Table<ReviewRuleCandidate>
          rowKey="id"
          loading={loading.list}
          dataSource={candidates}
          pagination={{
            current: query.page,
            pageSize: query.page_size,
            total,
            showSizeChanger: true,
          }}
          onChange={(pagination) => void handleTableChange(pagination)}
          columns={[
            { title: "Rule Name", dataIndex: "rule_name", ellipsis: true },
            { title: "Rule Type", dataIndex: "rule_type", width: 170 },
            { title: "Check Object", dataIndex: "check_object", width: 160, ellipsis: true },
            { title: "Operator", dataIndex: "operator", width: 90 },
            { title: "Threshold", dataIndex: "threshold_value", width: 110 },
            { title: "Unit", dataIndex: "unit", width: 80 },
            {
              title: "Confidence",
              dataIndex: "ai_confidence",
              width: 110,
              render: (value: number | null) => (value === null || value === undefined ? "-" : value.toFixed(2)),
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 150,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Actions",
              width: 90,
              render: (_, record) => (
                <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record)}>
                  Detail
                </Button>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="Rule Candidate Detail"
        open={Boolean(selected)}
        width={860}
        footer={
          selected ? (
            <Space>
              <Button onClick={() => setSelected(null)}>Close</Button>
              {isAdmin ? (
                <>
                  <Button icon={<SaveOutlined />} loading={loading.save} onClick={() => void save()}>
                    Save
                  </Button>
                  <Popconfirm title="Reject this candidate?" onConfirm={() => void reject(selected)}>
                    <Button danger icon={<StopOutlined />} loading={loading.reject}>
                      Reject
                    </Button>
                  </Popconfirm>
                  <Popconfirm title="Approve and publish as active review rule?" onConfirm={() => void approve(selected)}>
                    <Button type="primary" icon={<CheckCircleOutlined />} loading={loading.approve}>
                      Approve
                    </Button>
                  </Popconfirm>
                </>
              ) : null}
            </Space>
          ) : null
        }
        onCancel={() => setSelected(null)}
      >
        {selected ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card size="small" title="Source Clause">
              <Typography.Paragraph className="preserve-text">
                {selected.source_clause_text || "No source clause text"}
              </Typography.Paragraph>
            </Card>
            <Card size="small" title="AI Reason">
              <Typography.Paragraph className="preserve-text">{selected.ai_reason || "-"}</Typography.Paragraph>
            </Card>
            <Form form={editForm} layout="vertical" disabled={!isAdmin} requiredMark={false}>
              <Form.Item name="rule_name" label="Rule Name">
                <Input />
              </Form.Item>
              <Space align="start" style={{ width: "100%" }} className="form-space-row">
                <Form.Item name="rule_type" label="Rule Type" style={{ flex: 1 }}>
                  <Select options={ruleTypeOptions} allowClear />
                </Form.Item>
                <Form.Item name="work_type" label="Work Type" style={{ flex: 1 }}>
                  <Input />
                </Form.Item>
                <Form.Item name="risk_level_suggestion" label="Risk Level" style={{ flex: 1 }}>
                  <Select
                    allowClear
                    options={[
                      { value: "critical", label: "critical" },
                      { value: "major", label: "major" },
                      { value: "minor", label: "minor" },
                    ]}
                  />
                </Form.Item>
              </Space>
              <Space align="start" style={{ width: "100%" }} className="form-space-row">
                <Form.Item name="check_object" label="Check Object" style={{ flex: 1 }}>
                  <Input />
                </Form.Item>
                <Form.Item name="operator" label="Operator" style={{ width: 120 }}>
                  <Input />
                </Form.Item>
                <Form.Item name="threshold_value" label="Threshold" style={{ width: 150 }}>
                  <Input />
                </Form.Item>
                <Form.Item name="unit" label="Unit" style={{ width: 100 }}>
                  <Input />
                </Form.Item>
              </Space>
              <Form.Item name="required_items" label="Required Items">
                <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
              </Form.Item>
              <Form.Item name="forbidden_items" label="Forbidden Items">
                <Select mode="tags" tokenSeparators={[",", "，"]} open={false} />
              </Form.Item>
              <Form.Item name="applicable_condition" label="Applicable Condition JSON">
                <Input.TextArea rows={4} />
              </Form.Item>
              <Space align="start" style={{ width: "100%" }} className="form-space-row">
                <Form.Item name="ai_confidence" label="AI Confidence" style={{ width: 160 }}>
                  <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
                </Form.Item>
                <Form.Item name="status" label="Status" style={{ width: 190 }}>
                  <Select options={candidateStatusOptions} />
                </Form.Item>
              </Space>
            </Form>
          </Space>
        ) : null}
      </Modal>
    </div>
  );
};

const ruleTypeOptions = [
  { value: "required_section", label: "required_section" },
  { value: "required_field", label: "required_field" },
  { value: "required_keyword", label: "required_keyword" },
  { value: "forbidden_keyword", label: "forbidden_keyword" },
  { value: "parameter_threshold", label: "parameter_threshold" },
  { value: "procedure_required", label: "procedure_required" },
  { value: "semantic_check", label: "semantic_check" },
];

const candidateStatusOptions = [
  { value: "pending_review", label: "pending_review" },
  { value: "approved", label: "approved" },
  { value: "rejected", label: "rejected" },
];

const StatusTag = ({ status }: { status: string }) => {
  const color = status === "approved" ? "green" : status === "rejected" ? "red" : "orange";
  return <Tag color={color}>{status}</Tag>;
};

const normalizeCandidatePayload = (values: CandidateFormValues): ReviewRuleCandidatePayload | null => {
  try {
    return {
      ...values,
      applicable_condition: values.applicable_condition ? JSON.parse(values.applicable_condition) : {},
    };
  } catch {
    return null;
  }
};
