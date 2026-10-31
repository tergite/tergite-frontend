import {
  createBrowserRouter,
  createRoutesFromElements,
  Route,
} from "react-router-dom";
import { ErrorBoundary } from "react-error-boundary";
import ErrorAlert from "./pages/error-alert";
import LoginPage from "./pages/login";
import { Home, loader as homeLoader } from "./pages/home";
import { Devices, loader as devicesLoader } from "./pages/devices";
import { useAppStore } from "./lib/app-state";
import { queryClient } from "./lib/query-client";
import {
  Dashboard,
  loader as dashboardLoader,
} from "./components/layouts/dashboard";
import {
  DeviceDetail,
  loader as deviceDetailLoader,
} from "./pages/device-detail";
import { Tokens, loader as tokensLoader } from "./pages/tokens";
import { Projects, loader as projectsLoader } from "./pages/projects";
import {
  AdminProjects,
  loader as adminProjectsLoader,
} from "./pages/admin-projects";
import {
  AdminRequests,
  loader as adminRequestsLoader,
} from "./pages/admin-requests";
import {
  AdminControl,
  loader as adminControlLoader,
} from "./pages/admin-control";
import { Approvals, loader as approvalsLoader } from "./pages/approvals";
import { Settings, loader as settingsLoader } from "./pages/settings";
import { MyRequests, loader as myRequestsLoader } from "./pages/requests";

export const routes = createRoutesFromElements(
  <>
    <Route
      path="/"
      element={<Dashboard />}
      loader={dashboardLoader(queryClient)}
      errorElement={<ErrorAlert className="h-screen bg-muted" />}
    >
      <Route errorElement={<ErrorAlert />}>
        <Route index element={<Home />} loader={homeLoader(queryClient)} />
        <Route
          path="devices"
          element={<Devices />}
          loader={devicesLoader(queryClient)}
        />
        <Route
          path="devices/:deviceName"
          element={<DeviceDetail />}
          loader={deviceDetailLoader(queryClient)}
        />
        <Route
          path="tokens"
          element={<Tokens />}
          loader={tokensLoader(queryClient)}
        />
        <Route
          path="projects"
          element={<Projects />}
          loader={projectsLoader(queryClient)}
        />
        <Route
          path="approvals"
          element={<Approvals />}
          loader={approvalsLoader(queryClient)}
        />
        <Route
          path="requests"
          element={<MyRequests />}
          loader={myRequestsLoader(queryClient)}
        />
        <Route
          path="settings"
          element={<Settings />}
          loader={settingsLoader(queryClient)}
        />
        <Route
          path="admin-projects"
          element={<AdminProjects />}
          loader={adminProjectsLoader(queryClient)}
        />
        <Route
          path="admin-requests"
          element={<AdminRequests />}
          loader={adminRequestsLoader(queryClient)}
        />
        <Route
          path="admin-control"
          element={<AdminControl />}
          loader={adminControlLoader(queryClient)}
        />
      </Route>
    </Route>
    <Route
      path="login"
      element={
        <ErrorBoundary FallbackComponent={ErrorAlert}>
          <LoginPage />
        </ErrorBoundary>
      }
      errorElement={<ErrorAlert />}
    />
  </>,
);

/** Reruns the loaders when the selected project changes, as most of them read it */
export function revalidateOnProjectChange(
  router: ReturnType<typeof createBrowserRouter>,
) {
  return useAppStore.subscribe((state, previous) => {
    if (state.currentProjectId !== previous.currentProjectId) {
      router.revalidate();
    }
  });
}
