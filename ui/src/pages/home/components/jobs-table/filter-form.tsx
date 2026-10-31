import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { z } from "zod";

import {
  DataTableFilterField,
  DataTableFormConfig,
} from "@/components/ui/data-table";

export const jobFilterFormProps: DataTableFormConfig = {
  job_id: {
    validation: z.string(),
    defaultValue: "",
    label: "Job Id",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  device: {
    validation: z.string(),
    defaultValue: "",
    label: "Device",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  status: {
    validation: z.enum(["failed", "successful", "pending", ""]),
    defaultValue: "",
    label: "Status",
    getFormElement: ({ ref, value, ...props }: DataTableFilterField) => (
      <Select
        onValueChange={props.onChange}
        value={value as string | undefined}
        {...props}
      >
        <SelectTrigger ref={ref}>
          <SelectValue placeholder="Select status" />
        </SelectTrigger>
        <SelectContent data-cy-job-status-select>
          <SelectItem value="failed">Failed</SelectItem>
          <SelectItem value="successful">Successful</SelectItem>
          <SelectItem value="pending">Pending</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
