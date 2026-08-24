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
import { ReactElement, type MouseEventHandler } from "react";

export function ConfirmDialog({
  onConfirm,
  onCancel,
  onClose = () => {},
  trigger,
  title,
  description,
  confirmBtnLabel = "Confirm",
  cancelBtnLabel = "Cancel",
}: Props) {
  return (
    <Dialog
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent id="confirm-dialog">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="py-5">{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <div className="grid grid-cols-2 gap-2 w-full">
            <DialogClose asChild>
              <Button type="button" variant="default" onClick={onConfirm}>
                {confirmBtnLabel}
              </Button>
            </DialogClose>
            <DialogClose asChild>
              <Button
                type="button"
                variant="outline"
                className="text-destructive border-destructive"
                onClick={onCancel}
              >
                {cancelBtnLabel}
              </Button>
            </DialogClose>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  onConfirm?: MouseEventHandler<HTMLButtonElement>;
  onCancel?: MouseEventHandler<HTMLButtonElement>;
  onClose?: () => void;
  trigger: ReactElement;
  title: string;
  description: string;
  confirmBtnLabel?: string;
  cancelBtnLabel?: string;
}
