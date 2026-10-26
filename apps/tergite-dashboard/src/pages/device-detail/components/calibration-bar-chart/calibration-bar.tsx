import {
  type CalibrationDataPoint,
} from "@/pages/device-detail/components/calibration-points";
import { Bar } from "@visx/shape";
import { localPoint } from "@visx/event";
import { ScaleBand, ScaleLinear } from "@visx/vendor/d3-scale";

let tooltipTimeout: number;

export function CalibrationBar({
  record,
  xScale,
  yScale,
  yMax,
  hideTooltip,
  showTooltip,
}: Props) {
  const x = getXValue(record);
  const y = getYValue(record);
  const yMin = y != undefined ? yScale(y) : 0;

  const barWidth = xScale.bandwidth();
  const barHeight = yMax - (yMin ?? 0);
  const barX = xScale(x) ?? 0;
  const barY = yMax - barHeight;

  return (
    <Bar
      key={`bar-${x}`}
      x={barX}
      y={barY}
      width={barWidth}
      height={barHeight}
      className="fill-primary"
      onMouseLeave={() => {
        tooltipTimeout = window.setTimeout(() => {
          hideTooltip();
        }, 300);
      }}
      onMouseMove={(event) => {
        if (tooltipTimeout) clearTimeout(tooltipTimeout);
        // TooltipInPortal expects coordinates to be relative to containerRef
        // localPoint returns coordinates relative to the nearest SVG, which
        // is what containerRef is set to in this example.
        const eventSvgCoords = localPoint(event);
        const left = barX + barWidth / 2;
        showTooltip({
          tooltipData: record,
          tooltipTop: eventSvgCoords?.y,
          tooltipLeft: left,
        });
      }}
    />
  );
}

interface Props {
  record: CalibrationDataPoint;
  xScale: ScaleBand<number>;
  yScale: ScaleLinear<number, number, never>;
  yMax: number;
  hideTooltip: () => void;
  showTooltip: (args: {
    tooltipLeft?: number;
    tooltipTop?: number;
    tooltipData?: CalibrationDataPoint;
  }) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export function getYValue(item: CalibrationDataPoint) {
  return item.value;
}

// eslint-disable-next-line react-refresh/only-export-components
export function getXValue(item: CalibrationDataPoint) {
  return item.index;
}
