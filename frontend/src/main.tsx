import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
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
  BookOutlined,
  ExperimentOutlined,
  FileDoneOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  SnippetsOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import "@refinedev/antd/dist/reset.css";
import "./styles.css";

import { authProvider } from "./auth/authProvider";
import { AppHeader } from "./components/AppHeader";
import { DashboardPage } from "./pages/Dashboard";
import { LoginPage } from "./pages/LoginPage";
import { ModelCallPage } from "./pages/ModelCall";
import { PromptTestPage } from "./pages/PromptTest";
import { OpenKBPage } from "./pages/OpenKB";
import { TaskListPage } from "./pages/TaskList";
import { ConstructionPlanReviewPage, TemplateUploadPage } from "./pages/ConstructionPlanReview";
import { ChapterProfileJobsPage } from "./pages/ChapterProfileJobs";
import { ChapterProfileJobDetailPage } from "./pages/ChapterProfileJobDetail";
import { UtilsPPOcrPage } from "./pages/UtilsPPOcr";
import { ReviewTemplateListPage } from "./pages/ReviewTemplateList";
import { ReviewTemplateEditPage } from "./pages/ReviewTemplateEdit";
import { TemplateSectionRulesPage } from "./pages/TemplateSectionRules";
import { StandardClausesPage } from "./pages/StandardClauses";
import { CheckpointGenerationJobsPage } from "./pages/CheckpointGenerationJobs";
import { ReviewCheckpointsPage } from "./pages/ReviewCheckpoints";
import { ReviewTaskDetailPage } from "./pages/ReviewTaskDetail";
import { ReviewTasksPage } from "./pages/ReviewTasks";

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
    name: "prompt-test",
    list: "/prompt-test",
    meta: { label: "Prompt Test", icon: <ExperimentOutlined /> },
  },
  {
    name: "openkb",
    list: "/openkb",
    meta: { label: "OpenKB", icon: <DatabaseOutlined /> },
  },
  {
    name: "construction-review",
    meta: { label: "Review of Construction Plan", icon: <FileTextOutlined /> },
  },
  {
    name: "construction-plan",
    list: "/construction-plan",
    meta: { label: "Upload Construction Plan", icon: <FileSearchOutlined />, parent: "construction-review" },
  },
  {
    name: "construction-plan-profile-jobs",
    list: "/construction-plan/profile-jobs",
    meta: { label: "Profile Parsing", icon: <NodeIndexOutlined />, parent: "construction-review" },
  },
  {
    name: "upload-templates",
    list: "/upload-templates",
    meta: { label: "Upload Templates", icon: <SnippetsOutlined />, parent: "construction-review" },
  },
  {
    name: "review-templates",
    list: "/review-templates",
    meta: { label: "Templates Rules", icon: <SnippetsOutlined />, parent: "construction-review" },
  },
  {
    name: "checkpoint-generation",
    list: "/standards/checkpoint-generation",
    meta: { label: "Checkpoint Generation", icon: <BookOutlined />, parent: "construction-review" },
  },
  {
    name: "review-checkpoints",
    list: "/review-checkpoints",
    meta: { label: "Review Checkpoints", icon: <NodeIndexOutlined />, parent: "construction-review" },
  },
  {
    name: "review-tasks",
    list: "/review-tasks",
    meta: { label: "Review Tasks", icon: <FileDoneOutlined />, parent: "construction-review" },
  },
  {
    name: "utils",
    meta: { label: "Utils", icon: <ToolOutlined /> },
  },
  {
    name: "utils-ppocr",
    list: "/utils/ppocr",
    meta: { label: "PPOCR", icon: <FileSearchOutlined />, parent: "utils" },
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
                      Sider={(props) => (
                        <ThemedSiderV2
                          {...props}
                          fixed
                          render={({ items, dashboard }) => (
                            <>
                              {dashboard}
                              {items}
                            </>
                          )}
                        />
                      )}
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
                <Route path="/prompt-test" element={<PromptTestPage />} />
                <Route path="/openkb" element={<OpenKBPage />} />
                <Route path="/upload-templates" element={<TemplateUploadPage />} />
                <Route path="/construction-plan" element={<ConstructionPlanReviewPage />} />
                <Route path="/construction-plan/profile-jobs" element={<ChapterProfileJobsPage />} />
                <Route path="/construction-plan/profile-jobs/:id" element={<ChapterProfileJobDetailPage />} />
                <Route path="/review-templates" element={<ReviewTemplateListPage />} />
                <Route path="/review-templates/:id" element={<ReviewTemplateEditPage />} />
                <Route path="/review-templates/:id/section-rules" element={<TemplateSectionRulesPage />} />
                <Route path="/standards" element={<Navigate to="/standards/checkpoint-generation" replace />} />
                <Route path="/standards/checkpoint-generation" element={<CheckpointGenerationJobsPage />} />
                <Route path="/standards/:id/clauses" element={<StandardClausesPage />} />
                <Route path="/review-checkpoints" element={<ReviewCheckpointsPage />} />
                <Route path="/review-tasks" element={<ReviewTasksPage />} />
                <Route path="/review-tasks/:id" element={<ReviewTaskDetailPage />} />
                <Route path="/utils/ppocr" element={<UtilsPPOcrPage />} />
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
