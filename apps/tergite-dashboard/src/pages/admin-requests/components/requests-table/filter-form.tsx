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
import { UserRequestStatus, UserRequestType } from "../../../../../types";

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
    validation: z.nativeEnum(UserRequestType).or(z.literal("")),
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
          <SelectItem value={UserRequestType.CLOSE_PROJECT}>
            {UserRequestType.CLOSE_PROJECT}
          </SelectItem>
          <SelectItem value={UserRequestType.CREATE_PROJECT}>
            {UserRequestType.CREATE_PROJECT}
          </SelectItem>
          <SelectItem value={UserRequestType.PROJECT_ACCESS}>
            {UserRequestType.PROJECT_ACCESS}
          </SelectItem>
          <SelectItem value={UserRequestType.PROJECT_QPU_SECONDS}>
            {UserRequestType.PROJECT_QPU_SECONDS}
          </SelectItem>
          <SelectItem value={UserRequestType.TRANSFER_PROJECT}>
            {UserRequestType.TRANSFER_PROJECT}
          </SelectItem>
        </SelectContent>
      </Select>
    ),
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
        <SelectContent data-cy-user-request-status-select>
          <SelectItem value={UserRequestStatus.REJECTED}>Rejected</SelectItem>
          <SelectItem value={UserRequestStatus.APPROVED}>Approved</SelectItem>
          <SelectItem value={UserRequestStatus.PENDING}>Pending</SelectItem>
        </SelectContent>
      </Select>
    ),
  },
};
