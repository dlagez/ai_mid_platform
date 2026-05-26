import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { EyeOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Progress, Space, Table, Tag, Typography, message } from "antd";
import {
  listChapterProfileJobs,
  listDocuments,
  type ChapterProfileGenerationJob,
  type DocumentRecord,
} from "../services/documentService";

export const ChapterProfileJobsPage = () => {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ChapterProfileGenerationJob[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);

  const documentById = useMemo(() => {
    const map = new Map<number, DocumentRecord>();
    for (const document of documents) {
      map.set(document.id, document);
    }
    return map;
  }, [documents]);

  const load = async (nextPage = page, nextPageSize = pageSize) => {
    setLoading(true);
    try {
      const [jobResult, documentResult] = await Promise.all([
        listChapterProfileJobs({ page: nextPage, page_size: nextPageSize }),
        listDocuments({ document_type: "construction_plan" }),
      ]);
      setJobs(jobResult.items);
      setTotal(jobResult.total);
      setDocuments(documentResult);
      setPage(jobResult.page);
      setPageSize(jobResult.page_size);
    } catch {
      message.error("Failed to load chapter profile jobs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(1, pageSize);
  }, []);

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Profile Parsing</h1>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
          Reload
        </Button>
      </div>

      <Card>
        <Table<ChapterProfileGenerationJob>
          rowKey="id"
          loading={loading}
          dataSource={jobs}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (nextPage, nextPageSize) => void load(nextPage, nextPageSize),
          }}
          columns={[
            {
              title: "Job ID",
              dataIndex: "id",
              width: 90,
              render: (value: number) => `#${value}`,
            },
            {
              title: "Document",
              dataIndex: "document_id",
              ellipsis: true,
              render: (value: number) => {
                const document = documentById.get(value);
                return (
                  <Space direction="vertical" size={0}>
                    <Typography.Text>{document?.file_name ?? `Document #${value}`}</Typography.Text>
                    <Typography.Text type="secondary">ID: {value}</Typography.Text>
                  </Space>
                );
              },
            },
            {
              title: "Status",
              dataIndex: "status",
              width: 150,
              render: (value: string) => <ProfileStatusTag status={value} />,
            },
            {
              title: "Progress",
              width: 220,
              render: (_, record) => {
                const percent = record.total_sections
                  ? Math.round((record.processed_sections / record.total_sections) * 100)
                  : 0;
                return (
                  <Space direction="vertical" size={0} style={{ width: "100%" }}>
                    <Typography.Text>
                      {record.processed_sections}/{record.total_sections}
                    </Typography.Text>
                    <Progress
                      size="small"
                      percent={percent}
                      status={record.status === "failed" ? "exception" : record.status === "success" ? "success" : "active"}
                    />
                  </Space>
                );
              },
            },
            {
              title: "Result",
              width: 220,
              render: (_, record) => (
                <Space wrap size={6}>
                  <Tag color="green">created {record.created_count}</Tag>
                  <Tag color="blue">updated {record.updated_count}</Tag>
                  <Tag color="gold">rule {record.rule_only_count}</Tag>
                  <Tag color={record.failed_count ? "red" : "default"}>failed {record.failed_count}</Tag>
                </Space>
              ),
            },
            {
              title: "Started At",
              dataIndex: "started_at",
              width: 180,
              render: formatDate,
            },
            {
              title: "Finished At",
              dataIndex: "finished_at",
              width: 180,
              render: formatDate,
            },
            {
              title: "",
              width: 120,
              render: (_, record) => (
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/construction-plan/profile-jobs/${record.id}`)}
                >
                  Detail
                </Button>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
};

const ProfileStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success" ? "green" : status === "partial_success" || status === "rule_only" ? "gold" : status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatDate = (value: string | null) => (value ? new Date(value).toLocaleString() : "-");
