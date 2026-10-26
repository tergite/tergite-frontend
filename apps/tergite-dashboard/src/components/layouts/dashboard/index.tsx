import { TooltipProvider } from "../../ui/tooltip";
import { Sidebar } from "./components/sidebar";
import { Topbar } from "./components/topbar";
import { TopBanner } from "./components/top-banner";
import {
  Outlet,
  useLoaderData,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { logout, currentUserQuery } from "@/lib/api/auth";
import { myActiveProjectsQuery } from "@/lib/api/projects";
import { getAllUserRequestsQuery } from "@/lib/api/requests";
import { type User } from "@/lib/api/types";
import { useCallback, useMemo, useState } from "react";
import { useAppStore } from "@/lib/app-state";
import { ErrorBoundary } from "react-error-boundary";
import ErrorAlert from "@/pages/error-alert";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { Toaster } from "@/components/ui/toaster";
import { Footer } from "./components/footer";

export function Dashboard() {
  const { currentUser, isUserAdmin } = useLoaderData() as DashboardData;

  const { data: projects = [] } = useQuery(myActiveProjectsQuery);
  const personalProject = useMemo(
    () => projects.filter((v) => v.is_personal)[0],
    [projects],
  );
  const appState = useAppStore();
  const queryClient = useQueryClient();
  const location = useLocation();
  const isAdminScreen = useMemo(
    () => location.pathname.startsWith("/admin-"),
    [location.pathname],
  );
  const [isExpanded, setIsExpanded] = useState(true);
  const navigate = useNavigate();
  const contentAreaPaddingCls = isExpanded ? "sm:pl-56" : "sm:pl-20";
  const darkModeCls = appState.isDark ? "dark" : "";
  const toggleIsExpanded = useCallback(() => {
    setIsExpanded(!isExpanded);
  }, [setIsExpanded, isExpanded]);
  const { data: userRequests = [] } = useQuery(
    getAllUserRequestsQuery({
      status: "pending",
      currentUser,
    })
  );
  const pendingRequestsCount = userRequests.length;

  const handleLogout = useCallback(() => {
    logout(queryClient, appState).then(() => navigate("/login"));
  }, [queryClient, appState, navigate]);

  return (
    <TooltipProvider>
      <div
        className={cn("flex h-screen w-full flex-col bg-muted/40", darkModeCls)}
      >
        <Sidebar
          isExpanded={isExpanded}
          onIsExpandedChange={toggleIsExpanded}
          pendingRequestsCount={pendingRequestsCount}
          isUserAdmin={isUserAdmin}
          personalProject={personalProject}
        />
        <div
          className={`flex flex-col sm:gap-4 h-full sm:pt-4 ${contentAreaPaddingCls}`}
        >
          <Topbar
            currentProject={useAppStore.getState().currentProjectId}
            onProjectChange={appState.setCurrentProjectId}
            projects={projects}
            onLogout={handleLogout}
            currentUser={currentUser}
            pendingRequestsTotal={pendingRequestsCount}
            isUserAdmin={isUserAdmin}
          />

          <TopBanner
            currentUser={currentUser}
            shouldShowApiToken={!isAdminScreen}
          />
          <ErrorBoundary FallbackComponent={ErrorAlert} resetKeys={[location]}>
            <Outlet />
          </ErrorBoundary>
          <Footer />
          <Toaster />
        </div>
      </div>
    </TooltipProvider>
  );
}

interface DashboardData {
  currentUser: User;
  isUserAdmin: boolean;
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<DashboardData> => {
    const currentUser = await queryClient.ensureQueryData(currentUserQuery);
    const isUserAdmin = currentUser.roles.includes("admin");
    return { currentUser, isUserAdmin };
  });
}
