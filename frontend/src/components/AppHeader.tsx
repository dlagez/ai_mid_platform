import { useGetIdentity, useLogout } from "@refinedev/core";
import { App, Button, Layout, Space, Tag, Typography } from "antd";
import { LogoutOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";

export const AppHeader = () => {
  const { data: user } = useGetIdentity<CurrentUser>();
  const { mutate: logout } = useLogout();
  const { modal } = App.useApp();

  const handleLogout = () => {
    modal.confirm({
      title: "确认登出",
      content: "您确定要退出登录吗？",
      okText: "确定",
      cancelText: "取消",
      onOk: () => logout(),
    });
  };

  return (
    <Layout.Header className="app-header">
      <Space>
        <Typography.Text strong>{user?.username ?? "User"}</Typography.Text>
        {user?.role ? <Tag color={user.role === "admin" ? "blue" : "default"}>{user.role}</Tag> : null}
      </Space>
      <Button icon={<LogoutOutlined />} onClick={handleLogout} />
    </Layout.Header>
  );
};
