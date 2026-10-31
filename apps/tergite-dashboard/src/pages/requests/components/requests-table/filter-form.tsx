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
import { UserRequestStatus } from "../../../../../types";
import { z } from "zod";

export const filterFormProps: DataTableFormConfig = {
  title: {
    validation: z.string(),
    defaultValue: "",
    label: "Request",
    getFormElement: (field: DataTableFilterField) => <Input {...field} />,
  },
  status: {
    validation: z.nativeEnum(UserRequestStatus).or(z.literal("")),
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
        <SelectContent data-cy-request-status-select>
          <SelectItem value={UserRequestStatus.PENDING}>Pending</SelectItem>
          <SelectItem value={UserRequestStatus.APPROVED}>Approved</SelectItem>
          <SelectItem value={UserRequestStatus.REJECTED}>Rejected</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
