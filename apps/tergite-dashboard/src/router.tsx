import {
  createRoutesFromElements,
  createBrowserRouter,
  Route,
  RouterProvider,
} from "react-router-dom";
import ErrorAlert, { ErrorBound } from "./pages/error-alert";
import LoginPage from "./pages/login";
import { Home, loader as homeLoader } from "./pages/home";
import { Devices, loader as devicesLoader } from "./pages/devices";
import { AppState } from "../types";
import { MutableRefObject, useContext, useEffect, useMemo, useRef } from "react";
import { AppStateContext } from "./lib/app-state";
import {
  Dashboard,
  loader as dashboardLoader,
} from "./components/layouts/dashboard";
import {
  DeviceDetail,
  loader as deviceDetailLoader,
} from "./pages/device-detail";
import { QueryClient, useQueryClient } from "@tanstack/react-query";
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

export function AppRouter({ routerConstructor }: Props) {
  const appState = useContext(AppStateContext);
  const queryClient = useQueryClient();
  const latestAppState = useRef(appState);
  const loadedProjectId = useRef(appState.currentProjectId);
  const router = useMemo(
    () =>
      routerConstructor(
        getRoutes(createLiveAppState(latestAppState), queryClient),
        { basename: import.meta.env.BASE_URL },
      ),
    [routerConstructor, queryClient],
  );

  useEffect(() => {
    latestAppState.current = appState;
    if (appState.currentProjectId !== loadedProjectId.current) {
      loadedProjectId.current = appState.currentProjectId;
      router.revalidate();
    }
  }, [appState, router]);

  return <RouterProvider router={router} />;
}

interface Props {
  routerConstructor: typeof createBrowserRouter;
}

/**
 * Generates a collection of routes that are aware of the app state
 *
 * @param appState - the global state of the application
 * @param queryClient - the react query client for making queries
 * @returns - the array of routes
 */
function getRoutes(appState: AppState, queryClient: QueryClient) {
  return createRoutesFromElements(
    <>
      <Route
        path="/"
        element={
          <ErrorBound>
            <Dashboard />
          </ErrorBound>
        }
        loader={dashboardLoader(appState, queryClient)}
        errorElement={<ErrorAlert className="h-screen bg-muted" />}
      >
        <Route errorElement={<ErrorAlert />}>
          <Route
            index
            element={
              <ErrorBound>
                <Home />
              </ErrorBound>
            }
            loader={homeLoader(appState, queryClient)}
          />
          <Route
            path="devices"
            element={
              <ErrorBound>
                <Devices />
              </ErrorBound>
            }
            loader={devicesLoader(appState, queryClient)}
          />
          <Route
            path="devices/:deviceName"
            element={
              <ErrorBound>
                <DeviceDetail />
              </ErrorBound>
            }
            loader={deviceDetailLoader(appState, queryClient)}
          />
          <Route
            path="tokens"
            element={
              <ErrorBound>
                <Tokens />
              </ErrorBound>
            }
            loader={tokensLoader(appState, queryClient)}
          />
          <Route
            path="projects"
            element={
              <ErrorBound>
                <Projects />
              </ErrorBound>
            }
            loader={projectsLoader(appState, queryClient)}
          />
          <Route
            path="approvals"
            element={
              <ErrorBound>
                <Approvals />
              </ErrorBound>
            }
            loader={approvalsLoader(appState, queryClient)}
          />
          <Route
            path="requests"
            element={
              <ErrorBound>
                <MyRequests />
              </ErrorBound>
            }
            loader={myRequestsLoader(appState, queryClient)}
          />
          <Route
            path="settings"
            element={
              <ErrorBound>
                <Settings />
              </ErrorBound>
            }
            loader={settingsLoader(appState, queryClient)}
          />
          <Route
            path="admin-projects"
            element={
              <ErrorBound>
                <AdminProjects />
              </ErrorBound>
            }
            loader={adminProjectsLoader(appState, queryClient)}
          />
          <Route
            path="admin-requests"
            element={
              <ErrorBound>
                <AdminRequests />
              </ErrorBound>
            }
            loader={adminRequestsLoader(appState, queryClient)}
          />
          <Route
            path="admin-control"
            element={
              <ErrorBound>
                <AdminControl />
              </ErrorBound>
            }
            loader={adminControlLoader(appState, queryClient)}
          />
        </Route>
      </Route>
      <Route
        path="login"
        element={
          <ErrorBound>
            <LoginPage />
          </ErrorBound>
        }
        errorElement={<ErrorAlert />}
      />
    </>,
  );
}

/**
 * An app state whose every read and call goes to the latest state, so loaders built once
 * still see the project chosen since
 */
function createLiveAppState(latest: MutableRefObject<AppState>): AppState {
  return {
    get currentProjectId() {
      return latest.current.currentProjectId;
    },
    get apiToken() {
      return latest.current.apiToken;
    },
    get isDark() {
      return latest.current.isDark;
    },
    setCurrentProjectId: (value) => latest.current.setCurrentProjectId(value),
    setApiToken: (value) => latest.current.setApiToken(value),
    toggleIsDark: () => latest.current.toggleIsDark(),
    clear: () => latest.current.clear(),
  };
}
