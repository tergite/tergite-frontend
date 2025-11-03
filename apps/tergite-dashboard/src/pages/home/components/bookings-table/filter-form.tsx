import { Input } from "@/components/ui/input";
import { z } from "zod";

import {
  DataTableFilterField,
  DataTableFormConfig,
} from "@/components/ui/data-table";

export const bookingFilterFormProps: DataTableFormConfig = {
  backend: {
    validation: z.string(),
    defaultValue: "",
    label: "Device",
    getFormElement: (field: DataTableFilterField) => (
      <Input {...field} className="" />
    ),
  },
};
