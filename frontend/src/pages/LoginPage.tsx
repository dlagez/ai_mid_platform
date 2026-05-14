import { useState } from "react";
import { useLogin } from "@refinedev/core";
import { Card, Form, Input, Button, Typography, theme, Space } from "antd";
import { ApiOutlined, UserOutlined, LockOutlined } from "@ant-design/icons";

export const LoginPage = () => {
  const { token } = theme.useToken();
  const { mutate: login, isLoading } = useLogin();
  const [form] = Form.useForm();

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: token.colorBgLayout,
      }}
    >
      <Card
        style={{ width: 400, boxShadow: token.boxShadow }}
        styles={{ body: { padding: 32 } }}
      >
        <Space direction="vertical" size={24} style={{ width: "100%" }}>
          <Space direction="vertical" size={8} style={{ width: "100%", textAlign: "center" }}>
            <ApiOutlined style={{ fontSize: 48, color: token.colorPrimary }} />
            <Typography.Title level={3} style={{ margin: 0 }}>
              AI Mid Platform
            </Typography.Title>
          </Space>

          <Form
            form={form}
            layout="vertical"
            onFinish={(values) => login(values)}
            requiredMark={false}
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: "Please enter your username" }]}
            >
              <Input
                size="large"
                prefix={<UserOutlined />}
                placeholder="Username"
                autoFocus
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: "Please enter your password" }]}
            >
              <Input.Password
                size="large"
                prefix={<LockOutlined />}
                placeholder="Password"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" block size="large" loading={isLoading}>
                Sign In
              </Button>
            </Form.Item>
          </Form>

          <Typography.Text type="secondary" style={{ textAlign: "center", display: "block", fontSize: 12 }}>
            Demo: admin / admin123 &nbsp;|&nbsp; operator / operator123
          </Typography.Text>
        </Space>
      </Card>
    </div>
  );
};
