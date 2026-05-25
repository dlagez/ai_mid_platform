import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  InputNumber,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { TablePaginationConfig } from "antd";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import {
  listCheckpointGenerationItems,
  listCheckpointGenerationJobs,
  type CheckpointGenerationItem,
  type CheckpointGenerationItemQuery,
  type CheckpointGenerationJob,
  type CheckpointGenerationJobQuery,
} from "../services/reviewCheckpointService";

type FilterValues = {
  standard_id?: number;
  status?: string;
};

export const CheckpointGenerationJobsPage = () => {
  const [jobs, setJobs] = useState<CheckpointGenerationJob[]>([]);
  const [items, setItems] = useState<CheckpointGenerationItem[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [itemTotal, setItemTotal] = useState(0);
  const [jobQuery, setJobQuery] = useState<CheckpointGenerationJobQuery>({ page: 1, page_size: 10 });
  const [itemQuery, setItemQuery] = useState<CheckpointGenerationItemQuery>({ page: 1, page_size: 20 });
  const [loading, setLoading] = useState({ jobs: false, items: false });
  const [form] = Form.useForm<FilterValues>();

  const loadJobs = async (nextQuery = jobQuery) => {
    setLoading((current) => ({ ...current, jobs: true }));
    try {
      const result = await listCheckpointGenerationJobs(nextQuery);
      setJobs(result.items);
      setJobTotal(result.total);
      setJobQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
    } catch {
      message.error("Failed to load checkpoint generation jobs.");
    } finally {
      setLoading((current) => ({ ...current, jobs: false }));
    }
  };

  const loadItems = async (nextQuery = itemQuery) => {
    setLoading((current) => ({ ...current, items: true }));
    try {
      const result = await listCheckpointGenerationItems(nextQuery);
      setItems(result.items);
      setItemTotal(result.total);
      setItemQuery({ ...nextQuery, page: result.page, page_size: result.page_size });
    } catch {
      message.error("Failed to load checkpoint generation details.");
    } finally {
      setLoading((current) => ({ ...current, items: false }));
    }
  };

  useEffect(() => {
    void loadJobs();
    void loadItems();
  }, []);

  const applyFilter = async () => {
    const values = form.getFieldsValue();
    const nextJobQuery = { ...values, page: 1, page_size: jobQuery.page_size ?? 10 };
    const nextItemQuery = { ...values, page: 1, page_size: itemQuery.page_size ?? 20 };
    await Promise.all([loadJobs(nextJobQuery), loadItems(nextItemQuery)]);
  };

  const refresh = async () => {
    await Promise.all([loadJobs(), loadItems()]);
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Checkpoint Generation</h1>
        <Button icon={<ReloadOutlined />} loading={loading.jobs || loading.items} onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      <Card>
        <Form form={form} layout="inline" className="table-filter-form">
          <Form.Item name="standard_id" label="Standard ID">
            <InputNumber min={1} precision={0} />
          </Form.Item>
          <Form.Item name="status" label="Status">
            <Select allowClear style={{ width: 170 }} options={generationStatusOptions} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SearchOutlined />} onClick={() => void applyFilter()}>
              Search
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="Generation Jobs">
        <Table<CheckpointGenerationJob>
          rowKey="id"
          loading={loading.jobs}
          dataSource={jobs}
          pagination={{
            current: jobQuery.page,
            pageSize: jobQuery.page_size,
            total: jobTotal,
            showSizeChanger: true,
          }}
          onChange={(pagination: TablePaginationConfig) =>
            void loadJobs({
              ...jobQuery,
              page: pagination.current ?? 1,
              page_size: pagination.pageSize ?? 10,
            })
          }
          columns={[
            { title: "Job ID", dataIndex: "id", width: 90 },
            { title: "Standard ID", dataIndex: "standard_id", width: 120 },
            {
              title: "Progress",
              width: 230,
              render: (_, record) => (
                <Progress
                  percent={progressPercent(record)}
                  size="small"
                  status={record.status === "failed" ? "exception" : record.status === "running" ? "active" : "normal"}
                />
              ),
            },
            { title: "Created", dataIndex: "created_count", width: 100 },
            { title: "Failed", dataIndex: "failed_count", width: 90 },
            { title: "Skipped", dataIndex: "skipped_count", width: 90 },
            {
              title: "Status",
              dataIndex: "status",
              width: 140,
              render: (value: string) => <GenerationStatusTag status={value} />,
            },
            { title: "Created At", dataIndex: "created_at", width: 190, render: formatTime },
            {
              title: "Message",
              dataIndex: "error_message",
              ellipsis: true,
              render: (value: string | null) => value || "-",
            },
          ]}
        />
      </Card>

      <Card title="Clause To Checkpoint Details">
        <Table<CheckpointGenerationItem>
          rowKey="id"
          loading={loading.items}
          dataSource={items}
          pagination={{
            current: itemQuery.page,
            pageSize: itemQuery.page_size,
            total: itemTotal,
            showSizeChanger: true,
          }}
          onChange={(pagination: TablePaginationConfig) =>
            void loadItems({
              ...itemQuery,
              page: pagination.current ?? 1,
              page_size: pagination.pageSize ?? 20,
            })
          }
          columns={[
            { title: "Job ID", dataIndex: "job_id", width: 90 },
            { title: "Clause ID", dataIndex: "clause_id", width: 100 },
            { title: "Clause No", dataIndex: "clause_no", width: 130 },
            { title: "Clause Title", dataIndex: "clause_title", width: 220, ellipsis: true },
            {
              title: "Checkpoint IDs",
              dataIndex: "checkpoint_ids",
              width: 240,
              render: (values: number[]) => <IdList values={values} />,
            },
            { title: "Created", dataIndex: "created_count", width: 90 },
            {
              title: "Status",
              dataIndex: "status",
              width: 130,
              render: (value: string) => <GenerationStatusTag status={value} />,
            },
            {
              title: "Message",
              dataIndex: "message",
              ellipsis: true,
              render: (value: string | null) => <Typography.Text>{value || "-"}</Typography.Text>,
            },
            { title: "Finished At", dataIndex: "finished_at", width: 190, render: formatTime },
          ]}
        />
      </Card>
    </div>
  );
};

const generationStatusOptions = [
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "success", label: "Success" },
  { value: "partial_success", label: "Partial Success" },
  { value: "failed", label: "Failed" },
  { value: "skipped", label: "Skipped" },
];

const progressPercent = (job: CheckpointGenerationJob) => {
  if (!job.total_clauses) {
    return 0;
  }
  return Math.round((job.processed_clauses / job.total_clauses) * 100);
};

const formatTime = (value?: string | null) => (value ? new Date(value).toLocaleString() : "-");

const IdList = ({ values }: { values: number[] }) => {
  if (!values?.length) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  return (
    <Space size={4} wrap>
      {values.map((value) => (
        <Tag key={value}>{value}</Tag>
      ))}
    </Space>
  );
};

const GenerationStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success"
      ? "green"
      : status === "partial_success"
        ? "gold"
        : status === "failed"
          ? "red"
          : status === "running"
            ? "blue"
            : "default";
  return <Tag color={color}>{status}</Tag>;
};
