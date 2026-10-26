import { DataTable } from "@/components/ui/data-table";
import { SortHeader } from "@/components/ui/data-table";
import type {
  CalibrationValue,
  DeviceCalibration,
  Qubit,
} from "@/lib/api/types";
import { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

export function CalibrationDataTable({ data }: Props) {
  const columns = useMemo(() => getColumns(data.qubits[0]), [data.qubits]);
  return <DataTable columns={columns} data={data.qubits} />;
}

interface Props {
  data: DeviceCalibration;
}

function getColumns(firstQubit: Qubit | undefined): ColumnDef<Qubit>[] {
  let units = {
    t1_decoherence: "",
    t2_decoherence: "",
    frequency: "",
    anharmonicity: "",
    readout_assignment_error: "",
  };

  if (firstQubit) {
    units = {
      t1_decoherence: ` (${firstQubit.t1_decoherence?.unit ?? ""})`,
      t2_decoherence: ` (${firstQubit.t2_decoherence?.unit ?? ""})`,
      frequency: ` (${firstQubit.frequency?.unit ?? ""})`,
      anharmonicity: ` (${firstQubit.anharmonicity?.unit ?? ""})`,
      readout_assignment_error: ` (${
        firstQubit.readout_assignment_error?.unit ?? ""
      })`,
    };
  }

  return [
    {
      id: "qubit",
      accessorFn: (_, index) => index,
      header: ({ column }) => <SortHeader label="Qubit" column={column} />,
      cell: ({ row }) => (
        <div className="font-medium">{row.getValue("qubit")}</div>
      ),
    },
    {
      id: "t1_decoherence",
      accessorFn: (row) => formatValue(row.t1_decoherence),
      header: ({ column }) => (
        <SortHeader label={`T1${units.t1_decoherence}`} column={column} />
      ),
    },
    {
      id: "t2_decoherence",
      accessorFn: (row) => formatValue(row.t2_decoherence),
      header: ({ column }) => (
        <SortHeader label={`T2${units.t2_decoherence}`} column={column} />
      ),
    },
    {
      id: "frequency",
      accessorFn: (row) => formatValue(row.frequency),
      header: ({ column }) => (
        <SortHeader label={`frequency${units.frequency}`} column={column} />
      ),
    },
    {
      id: "anharmonicity",
      accessorFn: (row) => formatValue(row.anharmonicity),
      header: ({ column }) => (
        <SortHeader
          label={`anharmonicity${units.anharmonicity}`}
          column={column}
        />
      ),
    },
    {
      id: "readout_assignment_error",
      accessorFn: (row) => formatValue(row.readout_assignment_error),
      header: ({ column }) => (
        <SortHeader
          label={`readout error${units.readout_assignment_error}`}
          column={column}
        />
      ),
    },
  ];
}

function formatValue(item?: CalibrationValue | null): string {
  if (typeof item?.value === "number") return item.value.toFixed(2);
  return `${item?.value ?? ""}`;
}
