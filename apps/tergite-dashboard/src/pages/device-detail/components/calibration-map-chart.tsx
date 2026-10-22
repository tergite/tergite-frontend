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
  const margin = { top: 20, right: 20, bottom: 20, left: 20 };
  const xMax = Math.max(width - margin.left - margin.right, 0);
  const yMax = Math.max(height - margin.top - margin.bottom, 0);

  const xValues = useMemo(
    () => [...new Set(device.coordinates.map((v) => v[0]))].sort((a, b) => a - b),
    [device]
  );
  const yValues = useMemo(
    () => [...new Set(device.coordinates.map((v) => v[1]))].sort((a, b) => a - b),
    [device]
  );

  const chatData: CalibrationDataPoint[] = useMemo(
    () =>
      data.qubits.map((v, index) => ({
        ...(v[currentProp] ?? {}),
        index,
      })),
    [data.qubits, currentProp]
  );

  const maxCurrentPropValue = useMemo(
    () =>
      Math.max(
        ...(chatData
          .map((v) => v.value)
          .filter((v) => v != undefined) as number[])
      ),
    [chatData]
  );

  // scales
  const xScale = useMemo(
    () =>
      scalePoint<number>({
        domain: xValues,
        padding: 0.2,
        range: [margin.left, xMax],
      }),
    [xValues, xMax, margin.left]
  );
  const yScale = useMemo(
    () =>
      scalePoint<number>({
        domain: yValues,
        padding: 0.2,
        range: [yMax, margin.top],
      }),
    [yValues, yMax, margin.top]
  );
  const minColorRangeValue = 0.3;
  const colorScale = useMemo(
    () =>
      scaleLinear<number>({
        domain: [0, maxCurrentPropValue],
        nice: true,
        range: [minColorRangeValue, 1],
      }),
    [maxCurrentPropValue]
  );

  const qubitIdx = useMemo(
    () => Object.fromEntries(device.qubit_ids.map((v, idx) => [v, idx])),
    [device.qubit_ids]
  );

  const qubits: QubitNode[] = useMemo(
    () =>
      device.coordinates.map(([x, y], idx) => ({
        x: xScale(x) ?? 0,
        y: yScale(y) ?? 0,
        data: chatData[idx],
        color: interpolatePurples(
          chatData[idx].value != undefined
            ? colorScale(chatData[idx].value as number) ?? minColorRangeValue
            : minColorRangeValue
        ),
      })),
    [chatData, device, xScale, yScale, colorScale]
  );

  const couplers: CouplerLink[] = useMemo(
    () =>
      Object.values(device.coupling_dict ?? {}).map(([srcQubit, dstQubit]) => ({
        source: qubits[qubitIdx[srcQubit]],
        target: qubits[qubitIdx[dstQubit]],
      })),
    [device, qubits, qubitIdx]
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
          graph={{
            nodes: qubits,
            links: couplers,
          }}
          top={margin.top}
          left={margin.left}
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
