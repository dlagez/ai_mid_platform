import { useState } from "react";
import { Button, Card, Form, Input, InputNumber, Select, Space, Typography, message } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { callModel } from "../services/modelService";

const defaultPrompt = "Summarize the purpose of an AI mid-platform in three bullet points.";

export const ModelCallPage = () => {
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState<string>("");

  const handleSubmit = async (values: { model: string; prompt: string; temperature: number; max_tokens: number }) => {
    setLoading(true);
    try {
      const result = await callModel({
        model: values.model,
        temperature: values.temperature,
        max_tokens: values.max_tokens,
        messages: [{ role: "user", content: values.prompt }],
      });
      setOutput(JSON.stringify(result.output, null, 2));
    } catch (error) {
      message.error("Model call failed. Confirm backend auth and LiteLLM configuration.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Model Call Panel</h1>
      </div>
      <Card>
        <Form
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            model: "gpt-4o-mini",
            prompt: defaultPrompt,
            temperature: 0.2,
            max_tokens: 1024,
          }}
        >
          <Form.Item name="model" label="Model" rules={[{ required: true }]}>
            <Select
              options={[
                { label: "gpt-4o-mini", value: "gpt-4o-mini" },
                { label: "gpt-4o", value: "gpt-4o" },
                { label: "claude-3-5-sonnet", value: "claude-3-5-sonnet" },
              ]}
            />
          </Form.Item>
          <Form.Item name="prompt" label="Prompt" rules={[{ required: true }]}>
            <Input.TextArea rows={7} />
          </Form.Item>
          <Space wrap>
            <Form.Item name="temperature" label="Temperature">
              <InputNumber min={0} max={2} step={0.1} />
            </Form.Item>
            <Form.Item name="max_tokens" label="Max tokens">
              <InputNumber min={1} max={8192} />
            </Form.Item>
          </Space>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} icon={<SendOutlined />}>
              Call Model
            </Button>
          </Form.Item>
        </Form>
      </Card>
      <Card title="Output">
        <Typography.Text className="model-output">
          {output || "Model response will appear here."}
        </Typography.Text>
      </Card>
    </div>
  );
};
