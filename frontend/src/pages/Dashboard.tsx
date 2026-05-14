import { Card, Col, Row, Statistic, Typography } from "antd";
import { ApiOutlined, CloudServerOutlined, DatabaseOutlined, ScheduleOutlined } from "@ant-design/icons";

export const DashboardPage = () => {
  return (
    <div className="page">
      <div className="page-heading">
        <h1>Dashboard</h1>
      </div>
      <div className="metric-grid">
        <Card className="metric-card">
          <Statistic title="Model Providers" value={1} prefix={<ApiOutlined />} />
        </Card>
        <Card className="metric-card">
          <Statistic title="Queued Tasks" value={0} prefix={<ScheduleOutlined />} />
        </Card>
        <Card className="metric-card">
          <Statistic title="Knowledge Collections" value={0} prefix={<DatabaseOutlined />} />
        </Card>
        <Card className="metric-card">
          <Statistic title="Object Buckets" value={2} prefix={<CloudServerOutlined />} />
        </Card>
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Platform Services">
            <Typography.Paragraph>
              FastAPI, Celery, PostgreSQL, Redis, MinIO, LiteLLM core module, and RAG adapter entry points
              are wired for local development.
            </Typography.Paragraph>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Security">
            <Typography.Paragraph>
              JWT authentication is integrated through Refine Auth. Backend routes use permission
              dependencies for RBAC.
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  );
};
