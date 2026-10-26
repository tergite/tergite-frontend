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
import { type ExtendedAppToken } from "@/lib/api/tokens";

export function TokenDeleteDialog({ token, onDelete, isDisabled }: Props) {
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
      <DialogContent id="delete-token-dialog">
        <DialogHeader>
          <DialogTitle>Delete token {token.title}?</DialogTitle>
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
              I want to delete this token
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  token: ExtendedAppToken;
  isDisabled: boolean;
  onDelete?: MouseEventHandler<HTMLButtonElement>;
}
