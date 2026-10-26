import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  type QubitProp,
} from "@/pages/device-detail/components/calibration-points";

export function PropSelector({ value, onValueChange, fieldLabels }: Props) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="w-fit focus:ring-0">
        <span className="hidden sm:inline text-muted-foreground pr-1">
          Property:{" "}
        </span>
        <SelectValue placeholder="Select property" />
      </SelectTrigger>
      <SelectContent id="prop-selector">
        {Object.keys(fieldLabels).map((prop) => (
          <SelectItem value={prop} key={prop}>
            {fieldLabels[prop]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

interface Props {
  value: QubitProp;
  onValueChange: (value: QubitProp) => void;
  fieldLabels: { [k: string]: string };
}
