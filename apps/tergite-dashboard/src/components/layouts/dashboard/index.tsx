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
import {
  logout,
  myActiveProjectsQuery,
  currentUserQuery,
  allUserRequestsQuery,
} from "@/lib/api-client";
import { AppState, User, UserRequestStatus, UserRole } from "../../../../types";
import { useCallback, useContext, useMemo, useState } from "react";
import { AppStateContext } from "@/lib/app-state";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn, loadOrRedirectIfAuthErr } from "@/lib/utils";
import { Toaster } from "@/components/ui/toaster";
import { Footer } from "./components/footer";

export function Dashboard() {
  const { currentUser, isUserAdmin } = useLoaderData() as DashboardData;

  const { data: projects = [] } = useQuery(myActiveProjectsQuery);
  const appState = useContext(AppStateContext);
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
    allUserRequestsQuery({
      status: UserRequestStatus.PENDING,
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
        />
        <div
          className={`flex flex-col sm:gap-4 h-full sm:pt-4 ${contentAreaPaddingCls}`}
        >
          <Topbar
            currentProject={appState.currentProjectExtId}
            onProjectChange={appState.setCurrentProjectExtId}
            projects={projects}
            onLogout={handleLogout}
            currentUser={currentUser}
            pendingRequestsTotal={pendingRequestsCount}
            isUserAdmin={isUserAdmin}
          />

          {!isAdminScreen && <TopBanner currentUser={currentUser} />}
          <Outlet />
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
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async () => {
    // current user
    const cachedCurrentUser = queryClient.getQueryData(
      currentUserQuery.queryKey
    );
    const currentUser =
      cachedCurrentUser ?? (await queryClient.fetchQuery(currentUserQuery));

    const isUserAdmin = currentUser.roles.includes(UserRole.ADMIN);

    return { currentUser, isUserAdmin } as DashboardData;
  });
}
