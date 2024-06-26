import React from 'react';
import { VictoryAxis, VictoryChart, VictoryHistogram, VictoryLabel } from 'victory';

export default function Histogram({ data, label }: Props) {
	return (
		<VictoryChart data-cy-histogram={label}>
			<VictoryLabel
				x={400}
				y={280}
				textAnchor={'middle'}
				text={label}
				style={[{ fill: '#374151', fontSize: 12 }]}
			/>
			{/* @ts-ignore-error */}
			<VictoryAxis
				tickCount={7}
				style={{
					axis: { stroke: '#9CA3AF' },
					tickLabels: { fontSize: 12, padding: 5, fill: '#9CA3AF' }
				}}
			/>
			{/* @ts-ignore-error */}
			<VictoryAxis
				dependentAxis
				style={{
					axis: { stroke: 0 },
					tickLabels: { fontSize: 12, padding: 5, fill: '#9CA3AF' },
					grid: { stroke: '#9CA3AF', strokeWidth: 1, strokeDasharray: '8' }
				}}
			/>

			{/* @ts-ignore-error */}
			<VictoryHistogram
				cornerRadius={0}
				binSpacing={3}
				style={{
					data: {
						fill: '#9CE0DD',
						stroke: 0
					}
				}}
				data={data}
				//comment out hard coded bins to let d3 decide what the bins should be
				//bins={[50, 55, 60, 65, 70, 75, 80]}
			/>
		</VictoryChart>
	);
}

interface Props {
	data: { x: number }[];
	label: string;
}
