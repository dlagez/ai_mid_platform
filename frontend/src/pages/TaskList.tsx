import { useState } from "react";
import { Button, Card, Form, Input, Space, Table, Typography, message } from "antd";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { createTask, getTask } from "../services/taskService";
import { StatusTag } from "../components/StatusTag";

type TaskRow = {
  task_id: string;
  status: string;
  result?: unknown;
};

export const TaskListPage = () => {
  const [form] = Form.useForm();
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [loading, setLoading] = useState(false);

  const handleCreate = async (values: { task_type: string; payload?: string }) => {
    setLoading(true);
    try {
      const task = await createTask({
        task_type: values.task_type,
        payload: values.payload ? JSON.parse(values.payload) : {},
      });
      setTasks((current) => [task, ...current]);
      form.resetFields();
    } catch (error) {
      message.error("Unable to create task. Check JSON payload and backend status.");
    } finally {
      setLoading(false);
    }
  };

  const refreshTask = async (taskId: string) => {
    const updated = await getTask(taskId);
    setTasks((current) => current.map((task) => (task.task_id === taskId ? updated : task)));
  };

  return (
    <div className="page">
      <div className="page-heading">
        <h1>Task List</h1>
      </div>
      <Card>
        <Form form={form} layout="inline" onFinish={handleCreate} initialValues={{ task_type: "demo" }}>
          <Form.Item name="task_type" rules={[{ required: true }]}>
            <Input placeholder="Task type" />
          </Form.Item>
          <Form.Item name="payload" style={{ minWidth: 360 }}>
            <Input placeholder='Payload JSON, e.g. {"source":"manual"}' />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} icon={<PlusOutlined />}>
              Create
            </Button>
          </Form.Item>
        </Form>
      </Card>
      <Card>
        <Table<TaskRow>
          rowKey="task_id"
          dataSource={tasks}
          pagination={false}
          columns={[
            { title: "Task ID", dataIndex: "task_id", ellipsis: true },
            {
              title: "Status",
              dataIndex: "status",
              width: 140,
              render: (status) => <StatusTag status={status} />,
            },
            {
              title: "Result",
              dataIndex: "result",
              render: (result) =>
                result ? (
                  <Typography.Text code>{JSON.stringify(result)}</Typography.Text>
                ) : (
                  <Typography.Text type="secondary">Pending</Typography.Text>
                ),
            },
            {
              title: "Actions",
              width: 120,
              render: (_, row) => (
                <Space>
                  <Button icon={<ReloadOutlined />} onClick={() => refreshTask(row.task_id)} />
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
};
