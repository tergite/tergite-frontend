import {
  CalibrationDataPoint,
  Device,
  DeviceCalibration,
  QubitProp,
} from "../../../../types";
import { useParentSize } from "@visx/responsive";
import { defaultStyles, useTooltip, useTooltipInPortal } from "@visx/tooltip";
import { useMemo } from "react";
import { Graph } from "@visx/network";
import { localPoint } from "@visx/event";
import { scaleLinear, scalePoint } from "@visx/scale";
import { interpolatePurples } from "d3-scale-chromatic";
import { Group } from "@visx/group";
import { getCalibrationPoints } from "./calibration-points";

const MARGIN = { top: 20, right: 20, bottom: 20, left: 20 };
const MIN_COLOR_RANGE_VALUE = 0.3;

let tooltipTimeout: number;

export function CalibrationMapChart({
  minWidth,
  data,
  device,
  currentProp,
  currentLabel,
}: Props) {
  const {
    parentRef,
    width: _width,
    height,
  } = useParentSize({ debounceTime: 50 });

  const width = Math.max(minWidth, _width);
  const layout = useMemo(
    () => computeQubitLayout(device, data, currentProp, { width, height }),
    [device, data, currentProp, width, height]
  );

  const {
    tooltipOpen,
    tooltipLeft,
    tooltipTop,
    tooltipData,
    hideTooltip,
    showTooltip,
  } = useTooltip<{ qubit: number; value: string }>();

  const { containerRef, TooltipInPortal } = useTooltipInPortal({
    // TooltipInPortal is rendered in a separate child of <body /> and positioned
    // with page coordinates which should be updated on scroll. consider using
    // Tooltip or TooltipWithBounds if you don't need to render inside a Portal
    scroll: true,
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
        <Graph<CouplerLink, QubitNode>
          graph={layout}
          top={MARGIN.top}
          left={MARGIN.left}
          nodeComponent={({ node: { data, color } }) => (
            <Group>
              <circle
                className="stroke-[1%] stroke-card"
                fill={color}
                r="5%"
                data-qubit={data.index}
                data-value={`${data.value?.toFixed(2) ?? ""} ${data.unit}`}
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
                  // @ts-ignore
                  const tooltipData = event.target.dataset;

                  tooltipData &&
                    showTooltip({
                      tooltipData,
                      tooltipTop: eventSvgCoords?.y,
                      tooltipLeft: eventSvgCoords?.x,
                    });
                }}
              />
              <text
                className="fill-background text-lg lg:text-xl  xl:text-2xl font-semibold"
                textAnchor="middle"
                alignmentBaseline="middle"
              >
                {data.index}
              </text>
            </Group>
          )}
          linkComponent={({ link: { source, target } }) => (
            <line
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              className="stroke-muted-foreground stroke-[2%]"
            />
          )}
        />
      </svg>

      {tooltipOpen && tooltipData && (
        <TooltipInPortal
          top={tooltipTop}
          left={tooltipLeft}
          style={defaultStyles}
        >
          <div className="bg-card text-card-foreground min-w-5 p-4 lg:text-lg">
            <div className="mb-4">
              <strong>Qubit {tooltipData.qubit}</strong>
            </div>
            <div>
              {currentLabel}
              {": "}
              <span className="font-semibold">{tooltipData.value}</span>
            </div>
          </div>
        </TooltipInPortal>
      )}
    </div>
  );
}

interface Props {
  data: DeviceCalibration;
  device: Device;
  currentProp: QubitProp;
  currentLabel: string;
  minWidth: number;
  fieldLabels: { [k: string]: string };
}

/** Places each qubit by its coordinates and colours it by its value of the property */
function computeQubitLayout(
  device: Device,
  calibration: DeviceCalibration,
  prop: QubitProp,
  size: { width: number; height: number }
): { nodes: QubitNode[]; links: CouplerLink[] } {
  const points = getCalibrationPoints(calibration, prop);
  const values = points
    .map((v) => v.value)
    .filter((v) => v != undefined) as number[];
  const xScale = scalePoint<number>({
    domain: getSortedUnique(device.coordinates.map((v) => v[0])),
    padding: 0.2,
    range: [MARGIN.left, Math.max(size.width - MARGIN.left - MARGIN.right, 0)],
  });
  const yScale = scalePoint<number>({
    domain: getSortedUnique(device.coordinates.map((v) => v[1])),
    padding: 0.2,
    range: [Math.max(size.height - MARGIN.top - MARGIN.bottom, 0), MARGIN.top],
  });
  const colorScale = scaleLinear<number>({
    domain: [0, Math.max(...values)],
    nice: true,
    range: [MIN_COLOR_RANGE_VALUE, 1],
  });

  const nodes = device.coordinates.map(([x, y], index) => ({
    x: xScale(x) ?? 0,
    y: yScale(y) ?? 0,
    data: points[index],
    color: interpolatePurples(
      points[index].value != undefined
        ? colorScale(points[index].value as number) ?? MIN_COLOR_RANGE_VALUE
        : MIN_COLOR_RANGE_VALUE
    ),
  }));
  const qubitIndex = Object.fromEntries(
    device.qubit_ids.map((v, index) => [v, index])
  );
  const links = Object.values(device.coupling_dict ?? {}).map(
    ([sourceQubit, targetQubit]) => ({
      source: nodes[qubitIndex[sourceQubit]],
      target: nodes[qubitIndex[targetQubit]],
    })
  );
  return { nodes, links };
}

function getSortedUnique(values: number[]): number[] {
  return [...new Set(values)].sort((a, b) => a - b);
}

interface QubitNode {
  x: number;
  y: number;
  data: CalibrationDataPoint;
  color: string;
}

interface CouplerLink {
  source: QubitNode;
  target: QubitNode;
}
