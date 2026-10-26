import { useFormContext } from "react-hook-form";
import {
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiInput } from "@/components/ui/multi-input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { UserEmailInput } from "./user-email-input";

/** The fields of a project's form, inside the create or the edit form */
export function ProjectFields({ isActiveDisabled = false }: Props) {
  const { control, register } = useFormContext<ProjectFieldValues>();

  return (
    <>
      <FormField
        control={control}
        name="name"
        render={({ field }) => (
          <FormItem>
            <FormControl>
              <div>
                <Label className="text-muted-foreground" htmlFor="name">
                  Name
                </Label>
                <Input id="name" type="string" {...field} />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="description"
        render={({ field }) => (
          <FormItem>
            <FormControl>
              <div>
                <Label
                  className="mr-2 text-muted-foreground"
                  htmlFor="description"
                >
                  Description
                </Label>
                <Textarea id="description" {...field} rows={4} />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="is_active"
        render={({ field }) => (
          <FormItem>
            <FormControl>
              <div className="flex justify-between">
                <Label
                  className="mr-2 text-muted-foreground"
                  htmlFor="is_active"
                >
                  Live
                </Label>
                <Switch
                  id="is_active"
                  onCheckedChange={field.onChange}
                  checked={field.value}
                  disabled={isActiveDisabled}
                  aria-disabled={isActiveDisabled}
                />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="qpu_seconds"
        render={() => (
          <FormItem>
            <FormControl>
              <div>
                <Label className="text-muted-foreground" htmlFor="qpu_seconds">
                  QPU seconds
                </Label>
                <Input
                  id="qpu_seconds"
                  type="number"
                  {...register("qpu_seconds", { valueAsNumber: true })}
                />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="admin_email"
        render={({ field }) => (
          <FormItem>
            <FormControl>
              <div>
                <Label className="text-muted-foreground" htmlFor="admin_email">
                  Admin email
                </Label>
                <UserEmailInput id="admin_email" type="email" {...field} />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="user_emails"
        render={({ field }) => (
          <FormItem>
            <FormControl>
              <div className="flex flex-col">
                <Label
                  className="text-muted-foreground mb-1"
                  htmlFor="user_emails"
                >
                  Member emails
                </Label>
                <MultiInput
                  id="user_emails"
                  type="email"
                  {...field}
                  InputComponent={UserEmailInput}
                />
              </div>
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </>
  );
}

interface Props {
  isActiveDisabled?: boolean;
}

interface ProjectFieldValues {
  name?: string;
  description?: string;
  is_active?: boolean;
  qpu_seconds?: number;
  admin_email?: string;
  user_emails?: string[];
}
