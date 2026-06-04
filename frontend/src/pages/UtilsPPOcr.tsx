import { useEffect, useRef, useState } from "react";
import {
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import {
  ApartmentOutlined,
  CloudUploadOutlined,
  EyeOutlined,
  FileMarkdownOutlined,
  InboxOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { PdfPreviewModal } from "../components/PdfPreviewModal";
import { SectionTreeViewer, findFirstSection, getSectionTreeKeys } from "../components/SectionTreeViewer";
import { fetchPdfPreviewUrl } from "../services/filePreviewService";
import {
  createPPOcrPdfJob,
  getPPOcrPdfJob,
  getPPOcrPdfMarkdown,
  getPPOcrPdfSections,
  listPPOcrPdfJobs,
  rebuildPPOcrPdfSections,
  retryPPOcrPdfPage,
  type PPOcrPdfJob,
  type PPOcrPdfJobDetail,
  type PPOcrPdfPage,
  type PPOcrPdfSectionsResult,
  type PPOcrResultSection,
  type PPOcrResultSectionFlat,
} from "../services/utilsService";

export const UtilsPPOcrPage = () => {
  const [jobs, setJobs] = useState<PPOcrPdfJob[]>([]);
  const jobsRef = useRef<PPOcrPdfJob[]>(jobs);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<PPOcrPdfJobDetail | null>(null);
  const selectedDetailRef = useRef<PPOcrPdfJobDetail | null>(selectedDetail);
  const [sectionsResult, setSectionsResult] = useState<PPOcrPdfSectionsResult | null>(null);
  const [selectedSection, setSelectedSection] = useState<PPOcrResultSection | null>(null);
  const [expandedSectionKeys, setExpandedSectionKeys] = useState<string[]>([]);
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState({
    jobs: false,
    upload: false,
    detail: false,
    markdown: false,
    retry: false,
    sections: false,
    rebuildSections: false,
  });
  const [pdfPreview, setPdfPreview] = useState({ open: false, title: "", url: "" });
  const sectionTree = sectionsResult ? buildSectionTree(sectionsResult.flat_sections, sectionsResult.sections) : [];

  const refreshJobs = async () => {
    setLoading((s) => ({ ...s, jobs: true }));
    try {
      const nextJobs = await listPPOcrPdfJobs();
      jobsRef.current = nextJobs;
      setJobs(nextJobs);
      const selectedDetail = selectedDetailRef.current;
      if (selectedDetail) {
        const updated = nextJobs.find((job) => job.id === selectedDetail.job.id);
        if (updated) {
          const detail = await getPPOcrPdfJob(updated.id);
          selectedDetailRef.current = detail;
          setSelectedDetail(detail);
          if (["success", "partial_success", "failed"].includes(detail.job.status)) {
            const result = await getPPOcrPdfMarkdown(detail.job.id);
            setMarkdown(result.markdown);
            await loadSections(detail.job.id, false);
          }
        }
      }
      startPollingIfActive(nextJobs);
    } catch {
      message.error("Failed to load PPOCR jobs.");
    } finally {
      setLoading((s) => ({ ...s, jobs: false }));
    }
  };

  const refreshJobProgress = async () => {
    try {
      const nextJobs = await listPPOcrPdfJobs();
      jobsRef.current = nextJobs;
      setJobs(nextJobs);
      const currentDetail = selectedDetailRef.current;
      if (currentDetail) {
        const updated = nextJobs.find((job) => job.id === currentDetail.job.id);
        if (updated && ["queued", "running"].includes(updated.status)) {
          const detail = await getPPOcrPdfJob(updated.id);
          selectedDetailRef.current = detail;
          setSelectedDetail(detail);
        }
      }
      const hasActive = nextJobs.some((job) => ["queued", "running"].includes(job.status));
      if (!hasActive) {
        stopPolling();
      }
    } catch {
      // Silently ignore progress refresh errors.
    }
  };

  const pollingTimerRef = useRef<ReturnType<typeof window.setInterval> | null>(null);

  const stopPolling = () => {
    if (pollingTimerRef.current !== null) {
      window.clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  };

  const startPollingIfActive = (currentJobs: PPOcrPdfJob[]) => {
    if (currentJobs.some((job) => ["queued", "running"].includes(job.status))) {
      if (pollingTimerRef.current === null) {
        pollingTimerRef.current = window.setInterval(() => {
          void refreshJobProgress();
        }, 3000);
      }
    }
  };

  useEffect(() => {
    void refreshJobs();
    return () => stopPolling();
  }, []);

  const handleUpload = async () => {
    const originFile = fileList[0]?.originFileObj;
    if (!originFile) {
      message.warning("Select a PDF first.");
      return;
    }
    setLoading((s) => ({ ...s, upload: true }));
    try {
      const job = await createPPOcrPdfJob(originFile);
      setFileList([]);
      await refreshJobs();
      await handleViewJob(job.id);
      message.success("PDF uploaded. Page OCR tasks queued.");
    } catch {
      message.error("Failed to create PPOCR PDF job.");
    } finally {
      setLoading((s) => ({ ...s, upload: false }));
    }
  };

  const handleViewJob = async (jobId: number) => {
    setLoading((s) => ({ ...s, detail: true }));
    try {
      const detail = await getPPOcrPdfJob(jobId);
      selectedDetailRef.current = detail;
      setSelectedDetail(detail);
      if (["success", "partial_success", "failed"].includes(detail.job.status)) {
        setLoading((s) => ({ ...s, markdown: true }));
        const result = await getPPOcrPdfMarkdown(jobId);
        setMarkdown(result.markdown);
        setLoading((s) => ({ ...s, markdown: false }));
        await loadSections(jobId);
      } else {
        setMarkdown("");
        setSectionsResult(null);
        setSelectedSection(null);
      }
    } catch {
      message.error("Failed to load job detail.");
    } finally {
      setLoading((s) => ({ ...s, detail: false, markdown: false }));
    }
  };

  const loadSections = async (jobId: number, showError = true) => {
    setLoading((s) => ({ ...s, sections: true }));
    try {
      const result = await getPPOcrPdfSections(jobId);
      const nextTree = buildSectionTree(result.flat_sections, result.sections);
      setSectionsResult(result);
      setExpandedSectionKeys(getSectionTreeKeys(nextTree));
      setSelectedSection(findFirstSection(nextTree));
    } catch {
      if (showError) {
        message.error("Failed to load document sections.");
      }
      setSectionsResult(null);
      setSelectedSection(null);
      setExpandedSectionKeys([]);
    } finally {
      setLoading((s) => ({ ...s, sections: false }));
    }
  };

  const handleRebuildSections = async (secondaryDecimalSplit = false) => {
    const jobId = selectedDetail?.job.id;
    if (!jobId) {
      return;
    }
    setLoading((s) => ({ ...s, rebuildSections: true }));
    try {
      const result = await rebuildPPOcrPdfSections(jobId, {
        strategy: "ppocr_toc_outline",
        use_toc_outline: true,
        secondary_decimal_split: secondaryDecimalSplit,
      });
      const nextTree = buildSectionTree(result.flat_sections, result.sections);
      setSectionsResult(result);
      setExpandedSectionKeys(getSectionTreeKeys(nextTree));
      setSelectedSection(findFirstSection(nextTree));
      message.success(secondaryDecimalSplit ? "三级目录解析完成。" : "目录解析完成。");
    } catch (error: unknown) {
      message.error(getErrorDetail(error) ?? "Failed to rebuild document sections.");
    } finally {
      setLoading((s) => ({ ...s, rebuildSections: false }));
    }
  };

  const handleRetryPage = async (page: PPOcrPdfPage) => {
    setLoading((s) => ({ ...s, retry: true }));
    try {
      await retryPPOcrPdfPage(page.job_id, page.page_no);
      await handleViewJob(page.job_id);
      await refreshJobs();
      message.success(`Page ${page.page_no} retry queued.`);
    } catch {
      message.error("Failed to retry page.");
    } finally {
      setLoading((s) => ({ ...s, retry: false }));
    }
  };

  const handlePreviewPdf = async (job: PPOcrPdfJob) => {
    try {
      const url = await fetchPdfPreviewUrl(`/utils/ppocr/pdf/jobs/${job.id}/source`);
      setPdfPreview({ open: true, title: job.file_name, url });
    } catch {
      message.error("PDF preview failed.");
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>PPOCR PDF</h1>
        <Button icon={<ReloadOutlined />} loading={loading.jobs} onClick={() => void refreshJobs()}>
          Refresh
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="Upload PDF">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Upload.Dragger
                beforeUpload={() => false}
                fileList={fileList}
                maxCount={1}
                accept=".pdf"
                onChange={({ fileList: next }) => setFileList(next)}
              >
                <p className="ant-upload-drag-icon">
                  <InboxOutlined />
                </p>
                <p className="ant-upload-text">Select PDF</p>
              </Upload.Dragger>
              <Button
                type="primary"
                block
                loading={loading.upload}
                icon={<CloudUploadOutlined />}
                onClick={() => void handleUpload()}
              >
                Upload and Queue OCR
              </Button>
            </Space>
          </Card>

          <Card title="Parse Jobs" style={{ marginTop: 16 }}>
            <Table<PPOcrPdfJob>
              rowKey="id"
              size="small"
              loading={loading.jobs}
              dataSource={jobs}
              pagination={{ pageSize: 8 }}
              columns={[
                {
                  title: "File",
                  dataIndex: "file_name",
                  ellipsis: true,
                  render: (value: string, job) => (
                    <Button type="link" size="small" className="table-link-button" onClick={() => void handlePreviewPdf(job)}>
                      {value}
                    </Button>
                  ),
                },
                {
                  title: "Status",
                  dataIndex: "status",
                  width: 116,
                  render: (value: string) => <ParseStatusTag status={value} />,
                },
                {
                  title: "Progress",
                  width: 110,
                  render: (_, job) => (
                    <Progress
                      size="small"
                      percent={job.page_count ? Math.round(((job.succeeded_pages + job.failed_pages) / job.page_count) * 100) : 0}
                    />
                  ),
                },
                {
                  title: "",
                  width: 76,
                  render: (_, job) => (
                    <Button
                      size="small"
                      icon={<EyeOutlined />}
                      loading={loading.detail && selectedDetail?.job.id === job.id}
                      onClick={() => void handleViewJob(job.id)}
                    >
                      View
                    </Button>
                  ),
                },
              ]}
              expandable={{
                expandedRowRender: (job) => (
                  <Space direction="vertical" size={2}>
                    <Typography.Text type="secondary">
                      Pages: {job.succeeded_pages}/{job.page_count} success, {job.failed_pages} failed
                    </Typography.Text>
                    <Typography.Text type="secondary">
                      Confidence: {formatConfidence(job.avg_confidence)} / Low quality pages: {job.low_confidence_pages}
                    </Typography.Text>
                    <Typography.Text type="secondary">Markdown: {job.result_markdown_path ?? "-"}</Typography.Text>
                    {job.error_message ? <Typography.Text type="danger">{job.error_message}</Typography.Text> : null}
                  </Space>
                ),
              }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card
            title={
              selectedDetail ? (
                <Button
                  type="link"
                  className="table-link-button"
                  onClick={() => void handlePreviewPdf(selectedDetail.job)}
                >
                  {selectedDetail.job.file_name}
                </Button>
              ) : (
                "Job Detail"
              )
            }
            loading={loading.detail}
          >
            {selectedDetail ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Space wrap>
                  <ParseStatusTag status={selectedDetail.job.status} />
                  <Tag>{selectedDetail.job.page_count} pages</Tag>
                  <Tag>DPI {selectedDetail.job.dpi}</Tag>
                  <Tag>Batch {selectedDetail.job.batch_size}</Tag>
                  <Tag color={selectedDetail.job.low_confidence_flag ? "orange" : "green"}>
                    avg {formatConfidence(selectedDetail.job.avg_confidence)}
                  </Tag>
                </Space>
                <Table<PPOcrPdfPage>
                  rowKey="id"
                  size="small"
                  dataSource={selectedDetail.pages}
                  pagination={{ pageSize: 8 }}
                  columns={[
                    { title: "Page", dataIndex: "page_no", width: 70 },
                    {
                      title: "Status",
                      dataIndex: "status",
                      width: 116,
                      render: (value: string) => <ParseStatusTag status={value} />,
                    },
                    {
                      title: "Blocks",
                      dataIndex: "block_count",
                      width: 76,
                    },
                    {
                      title: "Confidence",
                      dataIndex: "average_confidence",
                      width: 110,
                      render: (value: number | null, page) => (
                        <Tag color={page.low_confidence_flag ? "orange" : "green"}>{formatConfidence(value)}</Tag>
                      ),
                    },
                    { title: "Retries", dataIndex: "retry_count", width: 82 },
                    {
                      title: "",
                      width: 84,
                      render: (_, page) => (
                        <Button
                          size="small"
                          disabled={page.status === "running"}
                          loading={loading.retry}
                          onClick={() => void handleRetryPage(page)}
                        >
                          Retry
                        </Button>
                      ),
                    },
                  ]}
                  expandable={{
                    expandedRowRender: (page) => (
                      <pre className="page-markdown-preview">
                        {page.markdown_content || page.text || page.error_message || "No page content"}
                      </pre>
                    ),
                  }}
                />
              </Space>
            ) : (
              <Empty description="Select a parse job" />
            )}
          </Card>

          <Card
            style={{ marginTop: 16 }}
            title={
              <Space>
                <ApartmentOutlined />
                <span>Document Sections</span>
              </Space>
            }
            loading={loading.sections}
            extra={
              selectedDetail && ["success", "partial_success", "failed"].includes(selectedDetail.job.status) ? (
                <Space>
                  <Button size="small" onClick={() => void loadSections(selectedDetail.job.id)}>
                    Reload
                  </Button>
                  <Button
                    size="small"
                    icon={<ReloadOutlined />}
                    loading={loading.rebuildSections}
                    onClick={() => void handleRebuildSections(false)}
                  >
                    目录解析
                  </Button>
                  <Button
                    size="small"
                    loading={loading.rebuildSections}
                    onClick={() => void handleRebuildSections(true)}
                  >
                    三级目录解析
                  </Button>
                </Space>
              ) : null
            }
          >
            {selectedDetail ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                {sectionTree.length ? (
                  <SectionTreeViewer
                    sections={sectionTree}
                    selectedSection={selectedSection}
                    expandedKeys={expandedSectionKeys}
                    onExpand={setExpandedSectionKeys}
                    onSelectSection={setSelectedSection}
                    renderDetail={(section) => (
                      <>
                        <Space wrap>
                          <Typography.Title level={4} style={{ margin: 0 }}>
                            {section.title}
                          </Typography.Title>
                          <Tag>Level {section.title_level}</Tag>
                          {section.section_no ? <Tag color="blue">{section.section_no}</Tag> : null}
                        </Space>
                        <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
                          {section.content || "No content found for this section."}
                        </Typography.Paragraph>
                      </>
                    )}
                  />
                ) : (
                  <Empty description="No sections found. Run directory parsing after OCR finishes." />
                )}
              </Space>
            ) : (
              <Empty description="Select a parse job" />
            )}
          </Card>

          <Card
            style={{ marginTop: 16 }}
            title={
              <Space>
                <FileMarkdownOutlined />
                <span>Document Markdown</span>
              </Space>
            }
            extra={
              selectedDetail?.job.result_markdown_path ? (
                <Button
                  size="small"
                  loading={loading.markdown}
                  onClick={() => void handleViewJob(selectedDetail.job.id)}
                >
                  Reload
                </Button>
              ) : null
            }
          >
            {markdown ? <pre className="markdown-preview">{markdown}</pre> : <Empty description="Markdown is generated after pages finish" />}
          </Card>
        </Col>
      </Row>
      <PdfPreviewModal
        title={pdfPreview.title}
        url={pdfPreview.url}
        open={pdfPreview.open}
        onClose={() => setPdfPreview({ open: false, title: "", url: "" })}
      />
    </div>
  );
};

const ParseStatusTag = ({ status }: { status: string }) => {
  const color =
    status === "success" || status === "parsed"
      ? "green"
      : status === "partial_success"
        ? "orange"
        : status === "failed"
          ? "red"
          : "blue";
  return <Tag color={color}>{status}</Tag>;
};

const formatConfidence = (value: number | null) => {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toFixed(3);
};

const buildSectionTree = (
  flatSections: PPOcrResultSectionFlat[],
  fallbackTree: PPOcrResultSection[] = [],
): PPOcrResultSection[] => {
  if (!flatSections.length) {
    return fallbackTree;
  }

  const items = new Map<number, PPOcrResultSection>();
  flatSections.forEach((section) => {
    items.set(section.id, { ...section, children: [] });
  });

  const roots: PPOcrResultSection[] = [];
  flatSections.forEach((section) => {
    const item = items.get(section.id);
    if (!item) {
      return;
    }
    const parent = section.parent_id ? items.get(section.parent_id) : null;
    if (parent) {
      parent.children.push(item);
    } else {
      roots.push(item);
    }
  });

  return roots;
};

const getErrorDetail = (error: unknown) =>
  typeof error === "object" &&
  error !== null &&
  "response" in error &&
  typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === "string"
    ? (error as { response: { data: { detail: string } } }).response.data.detail
    : null;
