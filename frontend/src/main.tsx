import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Outlet, Route, Routes } from "react-router-dom";
import { Refine, Authenticated } from "@refinedev/core";
import {
  ErrorComponent,
  RefineThemes,
  ThemedLayoutV2,
  ThemedSiderV2,
  ThemedTitleV2,
  useNotificationProvider,
} from "@refinedev/antd";
import routerBindings, {
  CatchAllNavigate,
  NavigateToResource,
  UnsavedChangesNotifier,
} from "@refinedev/react-router-v6";
import { App as AntdApp, ConfigProvider } from "antd";
import {
  ApiOutlined,
  AppstoreOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import "@refinedev/antd/dist/reset.css";
import "./styles.css";

import { authProvider } from "./auth/authProvider";
import { AppHeader } from "./components/AppHeader";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/LoginPage";
import { ModelCallPage } from "./pages/ModelCall";
import { OpenKBPage } from "./pages/OpenKB";
import { TaskListPage } from "./pages/TaskList";
import { ConstructionPlanReviewPage } from "./pages/ConstructionPlanReview";

const resources = [
  {
    name: "dashboard",
    list: "/",
    meta: { label: "Dashboard", icon: <DashboardOutlined /> },
  },
  {
    name: "tasks",
    list: "/tasks",
    meta: { label: "Task List", icon: <AppstoreOutlined /> },
  },
  {
    name: "models",
    list: "/models",
    meta: { label: "Model Calls", icon: <RobotOutlined /> },
  },
  {
    name: "openkb",
    list: "/openkb",
    meta: { label: "OpenKB", icon: <DatabaseOutlined /> },
  },
  {
    name: "construction-plan",
    list: "/construction-plan",
    meta: { label: "Review of Construction Plan", icon: <FileTextOutlined /> },
  },
];

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConfigProvider theme={RefineThemes.Blue}>
        <AntdApp>
          <Refine
            authProvider={authProvider}
            routerProvider={routerBindings}
            resources={resources}
            notificationProvider={useNotificationProvider}
            options={{
              syncWithLocation: true,
              warnWhenUnsavedChanges: true,
              projectId: "ai-mid-platform",
            }}
          >
            <Routes>
              <Route
                element={
                  <Authenticated key="authenticated-routes" fallback={<CatchAllNavigate to="/login" />}>
                    <ThemedLayoutV2
                      Header={AppHeader}
                      Sider={(props) => <ThemedSiderV2 {...props} fixed />}
                      Title={({ collapsed }) => (
                        <ThemedTitleV2 collapsed={collapsed} text="AI Mid" icon={<ApiOutlined />} />
                      )}
                    >
                      <Outlet />
                    </ThemedLayoutV2>
                  </Authenticated>
                }
              >
                <Route index element={<DashboardPage />} />
                <Route path="/tasks" element={<TaskListPage />} />
                <Route path="/models" element={<ModelCallPage />} />
                <Route path="/openkb" element={<OpenKBPage />} />
                <Route path="/construction-plan" element={<ConstructionPlanReviewPage />} />
                <Route path="*" element={<ErrorComponent />} />
              </Route>

              <Route
                element={
                  <Authenticated key="auth-pages" fallback={<Outlet />}>
                    <NavigateToResource resource="dashboard" />
                  </Authenticated>
                }
              >
                <Route path="/login" element={<LoginPage />} />
              </Route>
            </Routes>
            <UnsavedChangesNotifier />
          </Refine>
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
