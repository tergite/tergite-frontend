import { Button } from "@/components/ui/button";
import {
  DialogHeader,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { type MouseEventHandler } from "react";
import { type Project } from "@/lib/api/types";

export function DeleteProjectDialog({ project, onDelete, isDisabled }: Props) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          disabled={isDisabled}
          variant="outline"
          className="w-full text-destructive"
        >
          Delete
        </Button>
      </DialogTrigger>
      <DialogContent id="delete-project-dialog">
        <DialogHeader>
          <DialogTitle>Delete project {project.name}?</DialogTitle>
          <DialogDescription className="text-center py-5">
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button
              type="button"
              variant="outline"
              className="mx-auto w-full"
              onClick={onDelete}
            >
              I want to delete this project
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  project: Project;
  isDisabled: boolean;
  onDelete?: MouseEventHandler<HTMLButtonElement>;
}
