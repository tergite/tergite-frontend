import { z } from "zod";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  DataTableFilterField,
  DataTableFormConfig,
} from "@/components/ui/data-table";

export const filterFormProps: DataTableFormConfig = {
  name: {
    validation: z.string(),
    defaultValue: "",
    label: "Name",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  admin_email: {
    validation: z.string(),
    defaultValue: "",
    label: "Admin",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  is_active: {
    validation: z
      .boolean()
      .or(z.enum(["", "false", "true"]))
      .optional(),
    defaultValue: "",
    label: "Status",
    getFormElement: ({ ref, value, ...props }: DataTableFilterField) => (
      <Select
        onValueChange={(v) =>
          props.onChange(v == "" ? undefined : v === "true")
        }
        value={String(value) as string | undefined}
        {...props}
      >
        <SelectTrigger ref={ref}>
          <SelectValue placeholder="Select status" />
        </SelectTrigger>
        <SelectContent data-cy-project-status-select>
          <SelectItem value="false">Expired</SelectItem>
          <SelectItem value="true">Live</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
