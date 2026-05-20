import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tree,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadFile } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  ApartmentOutlined,
  CloudUploadOutlined,
  EyeOutlined,
  FileMarkdownOutlined,
  InboxOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { PdfPreviewModal } from "../components/PdfPreviewModal";
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
  type SectionRebuildStrategy,
} from "../services/utilsService";

const { TextArea } = Input;

export const UtilsPPOcrPage = () => {
  const [jobs, setJobs] = useState<PPOcrPdfJob[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<PPOcrPdfJobDetail | null>(null);
  const [sectionsResult, setSectionsResult] = useState<PPOcrPdfSectionsResult | null>(null);
  const [selectedSection, setSelectedSection] = useState<PPOcrResultSection | null>(null);
  const [sectionStrategy, setSectionStrategy] = useState<SectionRebuildStrategy>("decimal_number");
  const [useTocOutline, setUseTocOutline] = useState(true);
  const [customPatterns, setCustomPatterns] = useState({
    level1_pattern: "^(?P<section_no>[一二三四五六七八九十百千万零〇两]+)[、.．]\\s*(?P<title>.+)$",
    level2_pattern: "^[（(](?P<section_no>[一二三四五六七八九十百千万零〇两]+)[）)]\\s*(?P<title>.+)$",
    level3_pattern: "^(?P<section_no>\\d{1,2})(?:[.．、]|\\s+)\\s*(?P<title>.+)$",
  });
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

  const refreshJobs = async () => {
    setLoading((s) => ({ ...s, jobs: true }));
    try {
      const nextJobs = await listPPOcrPdfJobs();
      setJobs(nextJobs);
      if (selectedDetail) {
        const updated = nextJobs.find((job) => job.id === selectedDetail.job.id);
        if (updated) {
          const detail = await getPPOcrPdfJob(updated.id);
          setSelectedDetail(detail);
          if (["success", "partial_success", "failed"].includes(detail.job.status)) {
            const result = await getPPOcrPdfMarkdown(detail.job.id);
            setMarkdown(result.markdown);
            await loadSections(detail.job.id, false);
          }
        }
      }
    } catch {
      message.error("Failed to load PPOCR jobs.");
    } finally {
      setLoading((s) => ({ ...s, jobs: false }));
    }
  };

  useEffect(() => {
    void refreshJobs();
  }, []);

  useEffect(() => {
    if (!jobs.some((job) => ["queued", "running"].includes(job.status))) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refreshJobs();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [jobs, selectedDetail]);

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
      setSectionsResult(result);
      setSelectedSection(findFirstSection(result.sections));
    } catch {
      if (showError) {
        message.error("Failed to load document sections.");
      }
      setSectionsResult(null);
      setSelectedSection(null);
    } finally {
      setLoading((s) => ({ ...s, sections: false }));
    }
  };

  const handleRebuildSections = async () => {
    const jobId = selectedDetail?.job.id;
    if (!jobId) {
      return;
    }
    setLoading((s) => ({ ...s, rebuildSections: true }));
    try {
      const result = await rebuildPPOcrPdfSections(jobId, {
        strategy: sectionStrategy,
        use_toc_outline: useTocOutline,
        level1_pattern: sectionStrategy === "custom" ? customPatterns.level1_pattern : null,
        level2_pattern: sectionStrategy === "custom" ? customPatterns.level2_pattern : null,
        level3_pattern: sectionStrategy === "custom" ? customPatterns.level3_pattern : null,
      });
      setSectionsResult(result);
      setSelectedSection(findFirstSection(result.sections));
      message.success("Document sections rebuilt.");
    } catch {
      message.error("Failed to rebuild document sections.");
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
                    onClick={() => void handleRebuildSections()}
                  >
                    Rebuild
                  </Button>
                </Space>
              ) : null
            }
          >
            {selectedDetail ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Row gutter={[12, 12]} align="top">
                  <Col xs={24} md={10}>
                    <Select<SectionRebuildStrategy>
                      value={sectionStrategy}
                      style={{ width: "100%" }}
                      options={[
                        { value: "decimal_number", label: "1 / 1.2 / 1.2.3" },
                        { value: "chinese_number", label: "一、/（一）/ 1." },
                        { value: "markdown_heading", label: "# / ## / ###" },
                        { value: "custom", label: "Custom regex" },
                      ]}
                      onChange={setSectionStrategy}
                    />
                  </Col>
                  <Col xs={24} md={14}>
                    <Space wrap>
                      <Switch checked={useTocOutline} onChange={setUseTocOutline} />
                      <Typography.Text type="secondary">Use TOC as outline</Typography.Text>
                    </Space>
                  </Col>
                </Row>

                {sectionStrategy === "custom" ? (
                  <Row gutter={[12, 12]}>
                    <Col xs={24} md={8}>
                      <Typography.Text type="secondary">Level 1 regex</Typography.Text>
                      <TextArea
                        autoSize
                        value={customPatterns.level1_pattern}
                        onChange={(event) =>
                          setCustomPatterns((current) => ({ ...current, level1_pattern: event.target.value }))
                        }
                      />
                    </Col>
                    <Col xs={24} md={8}>
                      <Typography.Text type="secondary">Level 2 regex</Typography.Text>
                      <TextArea
                        autoSize
                        value={customPatterns.level2_pattern}
                        onChange={(event) =>
                          setCustomPatterns((current) => ({ ...current, level2_pattern: event.target.value }))
                        }
                      />
                    </Col>
                    <Col xs={24} md={8}>
                      <Typography.Text type="secondary">Level 3 regex</Typography.Text>
                      <TextArea
                        autoSize
                        value={customPatterns.level3_pattern}
                        onChange={(event) =>
                          setCustomPatterns((current) => ({ ...current, level3_pattern: event.target.value }))
                        }
                      />
                    </Col>
                  </Row>
                ) : null}

                {sectionsResult?.sections.length ? (
                  <Row gutter={[16, 16]}>
                    <Col xs={24} lg={10}>
                      <div className="plan-section-tree">
                        <Tree
                          blockNode
                          defaultExpandAll
                          selectedKeys={selectedSection ? [String(selectedSection.id)] : []}
                          treeData={toSectionTreeData(sectionsResult.sections)}
                          onSelect={(keys) => {
                            const key = keys[0];
                            if (!key) {
                              return;
                            }
                            setSelectedSection(findSection(sectionsResult.sections, Number(key)));
                          }}
                        />
                      </div>
                    </Col>
                    <Col xs={24} lg={14}>
                      <div className="plan-section-content">
                        {selectedSection ? (
                          <>
                            <Space wrap>
                              <Typography.Title level={4} style={{ margin: 0 }}>
                                {selectedSection.title}
                              </Typography.Title>
                              <Tag>Level {selectedSection.title_level}</Tag>
                              {selectedSection.section_no ? <Tag color="blue">{selectedSection.section_no}</Tag> : null}
                            </Space>
                            <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
                              {selectedSection.content || "No content found for this section."}
                            </Typography.Paragraph>
                          </>
                        ) : (
                          <Empty description="Select a section" />
                        )}
                      </div>
                    </Col>
                  </Row>
                ) : (
                  <Empty description="No sections found. Select a strategy and rebuild after parsing." />
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

const toSectionTreeData = (sections: PPOcrResultSection[]): DataNode[] =>
  sections.map((section) => ({
    key: String(section.id),
    title: section.title,
    children: toSectionTreeData(section.children),
  }));

const findSection = (sections: PPOcrResultSection[], id: number): PPOcrResultSection | null => {
  for (const section of sections) {
    if (section.id === id) {
      return section;
    }
    const child = findSection(section.children, id);
    if (child) {
      return child;
    }
  }
  return null;
};

const findFirstSection = (sections: PPOcrResultSection[]): PPOcrResultSection | null => {
  const [first] = sections;
  return first ?? null;
};
