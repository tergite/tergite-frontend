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
  title: {
    validation: z.string(),
    defaultValue: "",
    label: "Title",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  project_name: {
    validation: z.string(),
    defaultValue: "",
    label: "Project",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  is_expired: {
    validation: z
      .boolean()
      .or(z.enum(["", "true", "false"]))
      .optional(),
    defaultValue: "",
    label: "Status",
    getFormElement: ({ ref, value, ...props }: DataTableFilterField) => (
      <Select
        onValueChange={(v) =>
          props.onChange(v === "" ? undefined : v === "true")
        }
        value={String(value) as string | undefined}
        {...props}
      >
        <SelectTrigger ref={ref}>
          <SelectValue placeholder="Select status" />
        </SelectTrigger>
        <SelectContent data-cy-token-status-select>
          <SelectItem value="false">Live</SelectItem>
          <SelectItem value="true">Expired</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
