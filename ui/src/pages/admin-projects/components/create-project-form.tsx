import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AdminProject } from "@/lib/api/types";
import { useCallback } from "react";
import { Button, IconButton } from "@/components/ui/button";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Form } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { ProjectFields } from "./project-fields";
import {
  createAdminProject,
  refreshAllAdminQueries,
  refreshMyProjectsQueries,
} from "@/lib/api/projects";
import { DateTime } from "luxon";
import { X } from "lucide-react";

const formSchema = z.object({
  name: z.string().min(1),
  admin_email: z.string().email().min(1),
  description: z.string().min(1),
  user_emails: z.string().email().min(1).array().default([]),
  qpu_seconds: z.number().min(0).default(0),
  is_active: z.boolean().default(true),
  is_pulse_allowed: z.boolean().default(false),
});

export function CreateProjectForm({
  className = "",
  onCreate,
  onCancel = () => {},
  onClose,
}: Props) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = DateTime.now();

  const createForm = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: `${now.toLocaleString()} project`,
      description: `Project created on ${now.toLocaleString()}`,
      is_active: true,
      is_pulse_allowed: false,
      qpu_seconds: 0,
      admin_email: "",
      user_emails: [],
    },
  });

  const projectCreation = useMutation({
    mutationFn: async (values: z.infer<typeof formSchema>) => {
      return await createAdminProject(values);
    },
    onSuccess: useCallback(
      async (project: AdminProject) => {
        // before the refresh, or it would clear a row picked meanwhile
        onCreate(project);
        await refreshMyProjectsQueries(queryClient);
        await refreshAllAdminQueries(queryClient);
        toast({ description: `Project ${project.name} created` });
      },
      [onCreate, toast, queryClient]
    ),
    throwOnError: true,
  });

  const handleCancel = useCallback(async () => {
    createForm.reset();
    onCancel();
  }, [createForm, onCancel]);

  // formState.isDirty stays set after the form is given another project's values
  const isFormDirty = Object.keys(createForm.formState.dirtyFields).length > 0;

  return (
    <Form {...createForm}>
      <form
        onSubmit={createForm.handleSubmit((values) => {
          return projectCreation.mutate(values);
        })}
        onReset={handleCancel}
        className={cn("overflow-hidden", className)}
      >
        <Card id="create-project">
          <CardHeader className="flex flex-row items-center bg-muted/50 justify-between space-y-0">
            <div className="grid gap-0.5">
              <CardTitle className="group flex items-center gap-2 text-lg">
                New project
              </CardTitle>
            </div>
            <IconButton Icon={X} variant="ghost" onClick={onClose} />
          </CardHeader>
          <CardContent className="p-6 text-sm xl:max-h-[60vh] overflow-y-auto">
            <div className="grid gap-3">
              <ul className="grid gap-4">
                <ProjectFields isActiveDisabled />
              </ul>
            </div>
          </CardContent>
          <CardFooter className="grid grid-cols-2 gap-2 border-t bg-muted/50 px-6 py-3">
            <Button
              disabled={projectCreation.isPending || !isFormDirty}
              type="submit"
              variant="default"
            >
              Submit
            </Button>

            <Button
              type="reset"
              disabled={projectCreation.isPending}
              variant="secondary"
              className="border"
            >
              Cancel
            </Button>
          </CardFooter>
        </Card>
      </form>
    </Form>
  );
}

interface Props {
  className?: string;
  onCreate: (project: AdminProject) => void;
  onCancel?: () => void;
  onClose: () => void;
}
