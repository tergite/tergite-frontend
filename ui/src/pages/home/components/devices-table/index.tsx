import type { Device } from "@/lib/api/types";
import { deviceTableColumns } from "./columns";
import { DataTable } from "@/components/ui/data-table";
import { useNavigate } from "react-router-dom";
import { Row } from "@tanstack/react-table";

export function DevicesTable({ data }: Props) {
  const navigate = useNavigate();
  const goToDevice = (row: Row<Device>) => {
    navigate(`/devices/${row.original.name}`);
  };
  return (
    <DataTable
      columns={deviceTableColumns}
      data={data}
      onRowClick={goToDevice}
    />
  );
}

interface Props {
  data: Device[];
}
