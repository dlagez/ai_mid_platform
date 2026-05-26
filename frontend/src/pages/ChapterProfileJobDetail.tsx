import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeftOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Progress, Space, Table, Tag, Typography, message } from "antd";
import {
  getChapterProfileJob,
  listChapterProfileJobItems,
  listChapterProfileJobProfiles,
  type ChapterProfileGenerationItem,
  type ChapterProfileGenerationJob,
  type ChapterReviewProfile,
} from "../services/documentService";

export const ChapterProfileJobDetailPage = () => {
  const { id } = useParams();
  const jobId = Number(id);
  const navigate = useNavigate();
  const [job, setJob] = useState<ChapterProfileGenerationJob | null>(null);
  const [items, setItems] = useState<ChapterProfileGenerationItem[]>([]);
  const [profiles, setProfiles] = useState<ChapterReviewProfile[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    if (!jobId) {
      return;
    }
    setLoading(true);
    try {
      const [jobResult, itemResult, profileResult] = await Promise.all([
        getChapterProfileJob(jobId),
        listChapterProfileJobItems(jobId, { page: 1, page_size: 500 }),
        listChapterProfileJobProfiles(jobId, { page: 1, page_size: 500 }),
      ]);
      setJob(jobResult);
      setItems(itemResult.items);
      setProfiles(profileResult.items);
    } catch {
      message.error("Failed to load chapter profile job.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [jobId]);

  const percent = job?.total_sections ? Math.round((job.processed_sections / job.total_sections) * 100) : 0;

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Chapter Profile Job #{jobId}</h1>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/construction-plan/profile-jobs")}>
            Back
          </Button>
          <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
            Reload
          </Button>
        </Space>
      </div>

      <Card>
        {job ? (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Descriptions size="small" column={4}>
              <Descriptions.Item label="Document ID">{job.document_id}</Descriptions.Item>
              <Descriptions.Item label="Status">
                <StatusTag status={job.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Processed">
                {job.processed_sections}/{job.total_sections}
              </Descriptions.Item>
              <Descriptions.Item label="Celery Task">{job.celery_task_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="Created">{job.created_count}</Descriptions.Item>
              <Descriptions.Item label="Updated">{job.updated_count}</Descriptions.Item>
              <Descriptions.Item label="Rule Only">{job.rule_only_count}</Descriptions.Item>
              <Descriptions.Item label="Failed">{job.failed_count}</Descriptions.Item>
              <Descriptions.Item label="Started At">{formatDate(job.started_at)}</Descriptions.Item>
              <Descriptions.Item label="Finished At">{formatDate(job.finished_at)}</Descriptions.Item>
            </Descriptions>
            <Progress percent={percent} status={job.status === "failed" ? "exception" : undefined} />
            {job.error_message ? <Typography.Text type="danger">{job.error_message}</Typography.Text> : null}
          </Space>
        ) : (
          <Typography.Text type="secondary">No job loaded.</Typography.Text>
        )}
      </Card>

      <Card title="Generated Profiles">
        <Table<ChapterReviewProfile>
          rowKey="id"
          loading={loading}
          dataSource={profiles}
          pagination={{ pageSize: 10 }}
          expandable={{
            expandedRowRender: (record) => (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Descriptions size="small" column={2}>
                  <Descriptions.Item label="Chapter Path">{record.chapter_path || "-"}</Descriptions.Item>
                  <Descriptions.Item label="Chapter Type">{record.chapter_type || "-"}</Descriptions.Item>
                  <Descriptions.Item label="Main Domain">{record.main_domain || "-"}</Descriptions.Item>
                  <Descriptions.Item label="Subdomains">{formatList(record.subdomains)}</Descriptions.Item>
                  <Descriptions.Item label="Materials">{formatList(record.materials)}</Descriptions.Item>
                  <Descriptions.Item label="Parameters">{formatList(record.mentioned_parameters)}</Descriptions.Item>
                  <Descriptions.Item label="Methods">{formatList(record.mentioned_methods)}</Descriptions.Item>
                  <Descriptions.Item label="Risks">{formatList(record.mentioned_risks)}</Descriptions.Item>
                  <Descriptions.Item label="Standards">{formatList(record.mentioned_standards)}</Descriptions.Item>
                  <Descriptions.Item label="Expected Missing">{formatList(record.expected_missing_objects)}</Descriptions.Item>
                </Descriptions>
                <Typography.Text strong>Construction Objects</Typography.Text>
                <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                  {JSON.stringify(record.construction_objects ?? [], null, 2)}
                </pre>
              </Space>
            ),
          }}
          columns={[
            {
              title: "Profile ID",
              dataIndex: "id",
              width: 100,
            },
            {
              title: "Section ID",
              dataIndex: "section_id",
              width: 100,
            },
            {
              title: "Chapter",
              dataIndex: "chapter_title",
              ellipsis: true,
              render: (value: string | null, record) => value || record.chapter_path || "-",
            },
            {
              title: "Summary",
              dataIndex: "summary",
              ellipsis: true,
              render: (value: string | null) => value || "-",
            },
            {
              title: "Confidence",
              dataIndex: "confidence",
              width: 110,
              render: (value: number | null) => (value == null ? "-" : Number(value).toFixed(2)),
            },
            {
              title: "Updated At",
              dataIndex: "updated_at",
              width: 170,
              render: formatDate,
            },
          ]}
        />
      </Card>

      <Card title="Section Queue Details">
        <Table<ChapterProfileGenerationItem>
          rowKey="id"
          loading={loading}
          dataSource={items}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: "Section ID", dataIndex: "section_id", width: 100 },
            {
              title: "Section",
              dataIndex: "section_title",
              ellipsis: true,
              render: (value: string | null, record) => value || record.section_path || "-",
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 130,
              render: (value: string) => <StatusTag status={value} />,
            },
            {
              title: "Profile ID",
              dataIndex: "profile_id",
              width: 100,
              render: (value: number | null) => value ?? "-",
            },
            {
              title: "LLM",
              dataIndex: "used_llm",
              width: 90,
              render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? "used" : "no"}</Tag>,
            },
            {
              title: "Confidence",
              dataIndex: "confidence",
              width: 110,
              render: (value: number | null) => (value == null ? "-" : Number(value).toFixed(2)),
            },
            {
              title: "Message",
              dataIndex: "message",
              ellipsis: true,
              render: (value: string | null) => value || "-",
            },
            {
              title: "Finished At",
              dataIndex: "finished_at",
              width: 170,
              render: formatDate,
            },
          ]}
        />
      </Card>
    </div>
  );
};

const StatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success" ? "green" : status === "partial_success" || status === "rule_only" ? "gold" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDate = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");

const formatList = (value: unknown[]) => (value.length ? value.join(", ") : "-");
