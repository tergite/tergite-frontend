import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import { HealthStatus } from "@/components/ui/health-status";
import { deleteMyProject, refreshMyProjectsQueries } from "@/lib/api/projects";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Project } from "types";
import { DeleteProjectDialog } from "./delete-dialog";
import { useMemo } from "react";
import { DateTime, Duration } from "luxon";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";

export function ProjectsSidebar(props: SidebarProps) {
  return props.project ? (
    <ProjectSummary {...(props as ProjectSummaryProps)} />
  ) : (
    <SidebarPlaceholder
      mainTitle="Project title"
      contentTitle="Project details"
      contentDetail="Click any row to show details here"
      className={props.className}
    />
  );
}

function ProjectSummary({
  project,
  className = "",
  onDelete,
  canDelete,
}: ProjectSummaryProps) {
  const queryClient = useQueryClient();
  const projectDeletion = useMutation({
    mutationFn: deleteMyProject,
    onSuccess: async () => {
      // before the refresh, or it would clear a row picked meanwhile
      onDelete(project.id);
      await refreshMyProjectsQueries(queryClient);
    },
    throwOnError: true,
  });

  const createdAt = useMemo(
    () => DateTime.fromISO(project.created_at).toRelative(),
    [project]
  );

  const qpuTime = useMemo(
    () => Duration.fromObject({ seconds: project.qpu_seconds }).toHuman(),
    [project]
  );

  return (
    <Card id="project-summary" className={cn("overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-start bg-muted/50 justify-between">
        <div className="grid gap-0.5">
          <CardTitle className="group flex items-center gap-2 text-lg">
            {project.name}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-6 text-sm">
        <div className="grid gap-3">
          <div className="font-semibold">Details</div>
          <ul className="grid gap-3">
            <DetailItem label="ID">{project.id}</DetailItem>
            <DetailItem label="Description">{project.description}</DetailItem>
            <DetailItem label="Status">
              <HealthStatus isHealthy={project.is_active} />
            </DetailItem>
            <DetailItem label="Available QPU time">{qpuTime}</DetailItem>
            <DetailItem label="Created at">{createdAt}</DetailItem>
          </ul>
        </div>
      </CardContent>
      {canDelete && (
        <CardFooter className="flex flex-row items-center border-t bg-muted/50 px-6 py-3">
          <DeleteProjectDialog
            project={project}
            onDelete={() => projectDeletion.mutate(project.id)}
            isDisabled={projectDeletion.isPending}
          />
        </CardFooter>
      )}
    </Card>
  );
}

interface SidebarProps {
  project?: Project;
  canDelete: boolean;
  className?: string;
  onDelete: (id: string) => void;
}

interface ProjectSummaryProps extends SidebarProps {
  project: Project;
}
