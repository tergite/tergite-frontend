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
  requester_name: {
    validation: z.string(),
    defaultValue: "",
    label: "Requested by",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
  type: {
    validation: z.enum([
      "close-project",
      "create-project",
      "project-access",
      "project-qpu-seconds",
      "project-pulse-access",
      "transfer-project",
      "",
    ]),
    defaultValue: "",
    label: "Type",
    getFormElement: ({ ref, value, ...props }: DataTableFilterField) => (
      <Select
        onValueChange={props.onChange}
        value={value as string | undefined}
        {...props}
      >
        <SelectTrigger id="request-type-select" ref={ref}>
          <SelectValue placeholder="Select type" />
        </SelectTrigger>
        <SelectContent data-cy-user-request-type-select>
          <SelectItem value="close-project">
            close-project
          </SelectItem>
          <SelectItem value="create-project">
            create-project
          </SelectItem>
          <SelectItem value="project-access">
            project-access
          </SelectItem>
          <SelectItem value="project-qpu-seconds">
            project-qpu-seconds
          </SelectItem>
          <SelectItem value="project-pulse-access">
            project-pulse-access
          </SelectItem>
          <SelectItem value="transfer-project">
            transfer-project
          </SelectItem>
        </SelectContent>
      </Select>
    ),
  },
  status: {
    validation: z.enum(["rejected", "approved", "pending", ""]),
    defaultValue: "",
    label: "Status",
    getFormElement: ({ ref, value, ...props }: DataTableFilterField) => (
      <Select
        onValueChange={props.onChange}
        value={value as string | undefined}
        {...props}
      >
        <SelectTrigger id="request-status-select" ref={ref}>
          <SelectValue placeholder="Select status" />
        </SelectTrigger>
        <SelectContent data-cy-user-request-status-select>
          <SelectItem value="rejected">Rejected</SelectItem>
          <SelectItem value="approved">Approved</SelectItem>
          <SelectItem value="pending">Pending</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
