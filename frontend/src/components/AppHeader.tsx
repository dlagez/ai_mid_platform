import { useGetIdentity, useLogout } from "@refinedev/core";
import { Layout, Button, Space, Typography, Tag } from "antd";
import { LogoutOutlined } from "@ant-design/icons";
import type { CurrentUser } from "../types/platform";

export const AppHeader = () => {
  const { data: user } = useGetIdentity<CurrentUser>();
  const { mutate: logout } = useLogout();

  return (
    <Layout.Header className="app-header">
      <Space>
        <Typography.Text strong>{user?.username ?? "User"}</Typography.Text>
        {user?.role ? <Tag color={user.role === "admin" ? "blue" : "default"}>{user.role}</Tag> : null}
      </Space>
      <Button icon={<LogoutOutlined />} onClick={() => logout()} />
    </Layout.Header>
  );
};
