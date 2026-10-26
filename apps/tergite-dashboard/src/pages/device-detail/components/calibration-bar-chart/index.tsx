import {
  type CalibrationDataPoint,
  type QubitProp,
} from "@/pages/device-detail/components/calibration-points";
import { type DeviceCalibration } from "@/lib/api/types";
import { useTooltip, useTooltipInPortal, defaultStyles } from "@visx/tooltip";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { Grid } from "@visx/grid";
import { scaleBand, scaleLinear } from "@visx/scale";
import { useParentSize } from "@visx/responsive";
import { useMemo } from "react";
import { CalibrationBar, getXValue, getYValue } from "./calibration-bar";
import { useAppStore } from "@/lib/app-state";
import { getCalibrationPoints } from "../calibration-points";

const tooltipStyles = {
  ...defaultStyles,
  backgroundColor: "hsl(var(--secondary-foreground))",
  color: "hsl(var(--secondary))",
  minWidth: "1.25rem",
};

export function CalibrationBarChart({
  data,
  minWidth,
  fieldLabels,
  currentProp,
}: Props) {
  const {
    parentRef,
    width: _width,
    height,
  } = useParentSize({ debounceTime: 50 });
  const isDark = useAppStore((state) => state.isDark);
  const graphColor = isDark ? "#f9fafb" : "black";

  const width = Math.max(minWidth, _width);
  const margin = { top: 50, right: 0, bottom: 0, left: 50 };
  const xMax = Math.max(width - margin.left, 0);
  const yMax = Math.max(height - margin.top - 100, 0);

  const currentPropLabel = fieldLabels[currentProp];

  const chartData = useMemo(
    () => getCalibrationPoints(data, currentProp),
    [data, currentProp]
  );

  const maxYValue = useMemo(
    () =>
      Math.max(
        ...(chartData.map(getYValue).filter((v) => v != undefined) as number[])
      ),
    [chartData]
  );
  const yAxisLabel = chartData[0]?.unit
    ? `${currentPropLabel} (${chartData[0].unit})`
    : currentPropLabel;

  const {
    tooltipOpen,
    tooltipLeft,
    tooltipTop,
    tooltipData,
    hideTooltip,
    showTooltip,
  } = useTooltip<CalibrationDataPoint>();

  const { containerRef, TooltipInPortal } = useTooltipInPortal({
    // TooltipInPortal is rendered in a separate child of <body /> and positioned
    // with page coordinates which should be updated on scroll. consider using
    // Tooltip or TooltipWithBounds if you don't need to render inside a Portal
    scroll: true,
  });

  // scales
  const xScale = scaleBand<number>({
    domain: chartData.map(getXValue),
    padding: 0.2,
    range: [0, xMax],
    round: true,
  });
  const yScale = scaleLinear<number>({
    domain: [0, maxYValue],
    nice: true,
    range: [yMax, 0],
  });

  return (
    <div ref={parentRef} className="relative w-full h-full overflow-auto">
      <svg ref={containerRef} width={width} height={height}>
        <rect
          x={0}
          y={0}
          width={width}
          height={height}
          rx={4}
          className="bg-transparent fill-transparent"
        />
        <Grid
          top={margin.top}
          left={margin.left}
          xScale={xScale}
          yScale={yScale}
          width={xMax}
          height={yMax}
          stroke="secondary-foreground"
          strokeOpacity={0.1}
          xOffset={xScale.bandwidth() / 2}
        />
        <Group top={margin.top} left={margin.left}>
          {chartData.map((record) => (
            <CalibrationBar
              key={record.index}
              record={record}
              xScale={xScale}
              yMax={yMax}
              yScale={yScale}
              hideTooltip={hideTooltip}
              showTooltip={showTooltip}
            />
          ))}
        </Group>
        <AxisBottom
          top={yMax + margin.top}
          left={margin.left}
          scale={xScale}
          tickLabelProps={{
            textAnchor: "middle",
            className: "text-sm fill-muted-foreground",
          }}
          label="Qubit"
          labelClassName="text-sm fill-muted-foreground"
          labelOffset={30}
          stroke={graphColor}
          tickStroke={graphColor}
        />
        <AxisLeft
          scale={yScale}
          top={margin.top}
          left={margin.left}
          label={yAxisLabel}
          labelOffset={30}
          labelClassName="text-sm fill-muted-foreground"
          tickLabelProps={{
            className: `text-sm fill-muted-foreground`,
          }}
          stroke={graphColor}
          tickStroke={graphColor}
        />
      </svg>

      {tooltipOpen && tooltipData && (
        <TooltipInPortal
          top={tooltipTop}
          left={tooltipLeft}
          style={tooltipStyles}
        >
          <div>
            <strong>Qubit {tooltipData.index}</strong>
          </div>
          <div>
            {tooltipData?.value?.toFixed(2)} {tooltipData.unit}
          </div>
        </TooltipInPortal>
      )}
    </div>
  );
}

interface Props {
  data: DeviceCalibration;
  minWidth: number;
  currentProp: QubitProp;
  fieldLabels: { [k: string]: string };
}
