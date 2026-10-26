import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import {
  deleteAdminProject,
  refreshAllAdminQueries,
  refreshMyProjectsQueries,
  updateAdminProject,
} from "@/lib/api/projects";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type AdminProject } from "@/lib/api/types";
import { useCallback, useMemo } from "react";
import { DateTime } from "luxon";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button, IconButton } from "@/components/ui/button";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Form } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { ProjectFields } from "./project-fields";
import { X } from "lucide-react";

const formSchema = z.object({
  name: z.string().min(1).optional(),
  admin_email: z.string().email().min(1).optional(),
  description: z.string().min(1).optional(),
  user_emails: z.string().email().min(1).array().optional(),
  qpu_seconds: z.number().min(0).optional(),
  is_active: z.boolean().optional(),
});

export function AdminProjectSummary({
  project,
  className = "",
  onDelete,
  onEdit,
  onClose,
}: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const editForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    // the remote REST API sometimes returns records that have undefined values for the
    // some keys. In order for the FORM to play nicely, we need to set these
    // to their defaults
    values: { ...project, description: project.description || "" },
  });

  const projectDeletion = useMutation({
    mutationFn: deleteAdminProject,
    onSuccess: useCallback(async () => {
      // before the refresh, or it would clear a row picked meanwhile
      onDelete(project.id);
      await refreshMyProjectsQueries(queryClient);
      await refreshAllAdminQueries(queryClient);
      toast({ description: `Project ${project.name} deleted` });
    }, [project, toast, onDelete, queryClient]),
    throwOnError: true,
  });

  const projectEdit = useMutation({
    mutationFn: useCallback(
      async (values: z.infer<typeof formSchema>) => {
        return await updateAdminProject(project.id, values);
      },
      [project]
    ),
    onSuccess: useCallback(async () => {
      onEdit(project.id);
      await refreshMyProjectsQueries(queryClient);
      await refreshAllAdminQueries(queryClient);
      toast({ description: `Project ${project.name} updated` });
    }, [project, onEdit, toast, queryClient]),
    throwOnError: true,
  });

  const createdAt = useMemo(
    () => DateTime.fromISO(project.created_at).toRelative(),
    [project]
  );

  const updatedAt = useMemo(
    () => DateTime.fromISO(project.updated_at).toRelative(),
    [project]
  );

  // A hack: for some reason editForm.formState.isDirty was not always right especially
  //   when one clicked on another project when they had just editted only the user_emails field but not submitted
  //   if the new project had everything in common with the project, except say the user_emails, editForm.formState.isDirty
  //   would still show that it is dirty yet it should reset whenever new values are passed to it during initialization
  const isFormDirty = Object.keys(editForm.formState.dirtyFields).length;

  return (
    <Form {...editForm}>
      <form
        onSubmit={editForm.handleSubmit((values) => {
          return projectEdit.mutate(values);
        })}
        className={cn("overflow-hidden", className)}
      >
        <Card id="project-summary">
          <CardHeader className="flex flex-row items-center bg-muted/50 justify-between space-y-0">
            <div className="grid gap-0.5">
              <CardTitle className="group flex items-center gap-2 text-lg">
                {project.name}
              </CardTitle>
            </div>
            <IconButton Icon={X} variant="ghost" onClick={onClose} />
          </CardHeader>
          <CardContent className="p-6 text-sm xl:max-h-[60vh] overflow-y-auto">
            <div className="grid gap-3">
              <ul className="grid gap-4">
                <ProjectFields />

                <DetailItem label="ID" className="flex-col">
                  {project.id}
                </DetailItem>
                <DetailItem label="Created" className="flex-col">
                  {createdAt}
                </DetailItem>
                <DetailItem label="Last updated" className="flex-col">
                  {updatedAt}
                </DetailItem>
              </ul>
            </div>
          </CardContent>
          <CardFooter className="grid grid-cols-2 gap-2 border-t bg-muted/50 px-6 py-3">
            <Button
              disabled={projectEdit.isPending || !isFormDirty}
              type="submit"
              variant="default"
            >
              Update
            </Button>

            <ConfirmDialog
              title={`Delete project ${project.name}?`}
              description="This action cannot be undone."
              onConfirm={() => projectDeletion.mutate(project.id)}
              trigger={
                <Button
                  type="button"
                  disabled={projectDeletion.isPending}
                  variant="outline"
                  className="text-destructive border-destructive"
                >
                  Delete
                </Button>
              }
            />
          </CardFooter>
        </Card>
      </form>
    </Form>
  );
}

interface Props {
  project: AdminProject;
  className?: string;
  onDelete: (id: string) => void;
  onEdit: (id: string) => void;
  onClose: () => void;
}
