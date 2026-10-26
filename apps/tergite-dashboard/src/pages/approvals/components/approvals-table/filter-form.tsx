import {
  DataTableFilterField,
  DataTableFormConfig,
} from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { z } from "zod";

export const filterFormProps: DataTableFormConfig = {
  title: {
    validation: z.string(),
    defaultValue: "",
    label: "Request",
    getFormElement: (field: DataTableFilterField) => <Input {...field} />,
  },
  requester_name: {
    validation: z.string(),
    defaultValue: "",
    label: "From",
    getFormElement: (field: DataTableFilterField) => <Input {...field} />,
  },
  status: {
    validation: z.enum(["pending", "approved", "rejected", ""]),
    defaultValue: "",
    label: "Status",
    getFormElement: ({ ref, value, ...props }: DataTableFilterField) => (
      <Select
        onValueChange={props.onChange}
        value={value as string | undefined}
        {...props}
      >
        <SelectTrigger id="approval-status-select" ref={ref}>
          <SelectValue placeholder="Select status" />
        </SelectTrigger>
        <SelectContent data-cy-approval-status-select>
          <SelectItem value="pending">Pending</SelectItem>
          <SelectItem value="approved">Approved</SelectItem>
          <SelectItem value="rejected">Rejected</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
