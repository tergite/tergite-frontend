import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import DonutChart from "../donut-chart";

describe("donut-chart", () => {
  const percentagePointsMap: { [key: number]: string } = {
    10: `100,0
    172.65425280053609,0
    100,100`,
    25: `100,0
    200,0
    200,100
    100,100`,
    30: `100,0
    200,0
    200,132.49196962329063
    100,100`,
    50: `100,0
    200,0
    200,200
    100,200
    100,100`,
    60: `100,0
    200,0
    200,200
    27.345747199463915,200
    100,100`,
    75: `100,0
    200,0
    200,200
    0,200
    0,100
    100,100`,
    90: `100,0
    200,0
    200,200
    0,200
    0,0
    27.345747199463915,0
    100,100`,
    100: `100,0
    200,0
    200,200
    0,200
    0,0
    100,0
    100,100`,
  };

  [10, 25, 30, 50, 60, 75, 90, 100].forEach((percentFill) => {
    it(`renders the percentage ${percentFill}`, () => {
      render(<DonutChart percentFill={percentFill} />);
      expect(screen.queryByText(`${percentFill}%`)).toBeInTheDocument();
    });

    it("renders the children if provided", () => {
      const randomNumber = Math.random() * 100;
      render(
        <DonutChart percentFill={percentFill}>
          <text id="">{randomNumber}</text>
        </DonutChart>
      );
      expect(screen.queryByText(`${randomNumber}`)).toBeInTheDocument();
      expect(screen.queryByText(`${percentFill}%`)).not.toBeInTheDocument();
    });

    it(`renders the donut to ${percentFill}%`, () => {
      render(<DonutChart percentFill={percentFill} />);
      const progressCircle = document.querySelector(
        "#progress-circle"
      ) as SVGCircleElement;
      const clipPath = document.querySelector(
        "#visible-polygon"
      ) as SVGClipPathElement;
      const visiblePolygon = clipPath.firstChild as SVGPolygonElement;

      expect(progressCircle.getAttribute("stroke")).toBe(
        "url(#donut-stroke-linear-grad)"
      );
      expect(progressCircle.getAttribute("r")).toBe("40%");
      expect(progressCircle.getAttribute("clip-path")).toBe(
        "url(#visible-polygon)"
      );
      expect(visiblePolygon.getAttribute("points")).toBe(
        percentagePointsMap[percentFill]
      );
    });
  });

  it("renders the given radius", () => {
    render(<DonutChart percentFill={60} radius={50} />);
    const clipPath = document.querySelector(
      "#visible-polygon"
    ) as SVGClipPathElement;
    const visiblePolygon = clipPath.firstChild as SVGPolygonElement;

    expect(visiblePolygon.getAttribute("points")).toBe(
      `50,0
    100,0
    100,100
    13.672873599731957,100
    50,50`
    );
  });

  ["10%", 10, "20", 30, "50%"].forEach((thickness) => {
    it("renders the given stroke-width", () => {
      render(<DonutChart percentFill={60} radius={50} thickness={thickness} />);
      const progressCircle = document.querySelector(
        "#progress-circle"
      ) as SVGCircleElement;
      const backgroundCircle = document.querySelector(
        "#background-circle"
      ) as SVGCircleElement;

      expect(progressCircle.getAttribute("stroke-width")).toBe(`${thickness}`);
      expect(backgroundCircle.getAttribute("stroke-width")).toBe(
        `${thickness}`
      );
    });
  });
});
