import { useMemo, PropsWithChildren } from "react";

export default function DonutChart({
  radius = 100,
  percentFill,
  thickness = "10%",
  children,
}: PropsWithChildren<Props>) {
  const viewBoxSize = useMemo(() => radius * 2, [radius]);
  const visiblePolygonPoints = useMemo(
    () => getVisiblePolygon(radius, percentFill),
    [radius, percentFill]
  );
  return (
    <svg
      aria-valuenow={percentFill}
      aria-valuemax={100}
      aria-valuemin={0}
      width={viewBoxSize}
      height={viewBoxSize}
      viewBox={`0 0 ${viewBoxSize} ${viewBoxSize}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle
        id="background-circle"
        cx="50%"
        cy="50%"
        r="40%"
        strokeWidth={thickness}
        className="fill-none stroke-muted"
      />
      {children || (
        <text
          x="38%"
          y="55%"
          className="fill-secondary-foreground font-semibold text-2xl"
        >
          {`${percentFill}%`}
        </text>
      )}
      <circle
        id="progress-circle"
        cx="50%"
        cy="50%"
        r="40%"
        stroke="url(#donut-stroke-linear-grad)"
        strokeWidth={thickness}
        className="fill-none"
        clipPath="url(#visible-polygon)"
      />

      <defs>
        <linearGradient
          id="donut-stroke-linear-grad"
          x1="0%"
          y1="0%"
          x2="0%"
          y2="150%"
          gradientUnits="userSpaceOnUse"
        >
          <stop style={{ stopColor: "hsl(var(--primary))" }} />
          <stop
            offset={1}
            style={{ stopColor: "hsl(var(--primary-foreground))" }}
          />
        </linearGradient>
        <clipPath id="visible-polygon">
          <polygon points={visiblePolygonPoints} />
        </clipPath>
      </defs>
    </svg>
  );
}

interface Props {
  radius?: number;
  percentFill: number;
  thickness?: number | string;
}

/**
 * Generates the points for the polygon for the visible part of the
 * donut chart
 *
 * @param radius - the radius of the circle
 * @param percentFill - the percentage that is filled in the circle
 * @returns - the clipPath's polygon's points
 */
function getVisiblePolygon(radius: number, percentFill: number): string {
  if (0 > percentFill || percentFill > 100) {
    throw new Error("percentFill should be between 0 and 100");
  }
  const initialX = radius;

  const maxAngle = 2 * Math.PI;
  const fillInRadians = (percentFill / 100) * maxAngle;
  const diameter = 2 * radius;
  const deg45 = Math.PI / 4;
  const deg90 = Math.PI / 2;
  const deg180 = Math.PI;
  const deg270 = Math.PI * 1.5;
  const deg360 = Math.PI * 2;
  const deg135 = deg45 * 3;
  const deg225 = deg45 * 5;
  const deg315 = deg45 * 7;

  if (deg45 >= fillInRadians) {
    // a triangle like:
    // ____
    // |  /
    // | /
    // |/
    const deltaX = radius * Math.tan(fillInRadians);
    return `${initialX},0
    ${initialX + deltaX},0
    ${initialX},${radius}`;
  } else if (deg135 >= fillInRadians) {
    // a polygon like
    // ____
    // |  |
    // |  |
    // |  /
    // | /
    const deltaY = radius * Math.tan(deg90 - fillInRadians);
    return `${initialX},0
    ${diameter},0
    ${diameter},${radius - deltaY}
    ${initialX},${radius}`;
  } else if (deg225 >= fillInRadians) {
    // a polygon like
    //  ____
    //  |  |
    //  |  |
    //  /  |
    // /   |
    // -----
    const deltaX = radius * Math.tan(fillInRadians - deg180);
    return `${initialX},0
    ${diameter},0
    ${diameter},${diameter}
    ${initialX - deltaX},${diameter}
    ${initialX},${radius}`;
  } else if (deg315 >= fillInRadians) {
    // a polygon like
    //      ____
    //      |   |
    //   |\ |   |
    //   | \|   |
    //   |      |
    //   |      |
    //    -------
    const deltaY = radius * Math.tan(fillInRadians - deg270);
    return `${initialX},0
    ${diameter},0
    ${diameter},${diameter}
    0,${diameter}
    0,${radius - deltaY}
    ${initialX},${radius}`;
  } else {
    // a polygon like
    //   _   ____
    //   |\ |   |
    //   | \|   |
    //   |      |
    //   |      |
    //    -------
    const deltaX = radius * Math.tan(deg360 - fillInRadians);
    return `${initialX},0
    ${diameter},0
    ${diameter},${diameter}
    0,${diameter}
    0,0
    ${radius - deltaX},0
    ${initialX},${radius}`;
  }
}
