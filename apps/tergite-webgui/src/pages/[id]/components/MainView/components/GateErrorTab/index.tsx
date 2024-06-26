import { Box, Flex } from '@chakra-ui/react';
import React, { useContext, useLayoutEffect } from 'react';
import { useQuery } from 'react-query';
import { BackendContext, useSelectionMaps } from '@/state/BackendContext';
import BoxPlot from './components/BoxPlot';
import DatePicker from '@/components/primitives/DatePicker';
import VisualizationSkeleton from '@/components/primitives/VisualizationSkeleton';
import { fetchVizualitationData } from '@/utils/api';
import ErrorAlert from '@/components/primitives/ErrorAlert';

export default function GateErrorTab({ backend }: Props) {
	const [state] = useContext(BackendContext);
	const { setSelectionMap } = useSelectionMaps();

	const { isLoading, data, error, refetch, isFetching } = useQuery(
		'gateError',
		async () =>
			await fetchVizualitationData({
				backend: `${backend}`,
				timeFrom: state.timeFrom,
				timeTo: state.timeTo,
				type: 'type3'
			})
	);

	useLayoutEffect(() => {
		setSelectionMap(false, false);
	}, []);

	if (error) return <ErrorAlert error={error as Error} />;
	if (isLoading || isFetching) return <VisualizationSkeleton />;

	return (
		<Box>
			<Flex flexDir={'row'} align={'center'} p={3}>
				<Box ml={'auto'} mr={'3em'}>
					<DatePicker refetchFunction={refetch}></DatePicker>
				</Box>
			</Flex>
			<BoxPlot
				data={data.gates.map((gate) => ({
					x: gate.id,
					y: gate.gate_err.map((e) => e.value)
				}))}
			></BoxPlot>
		</Box>
	);
}

interface Props {
	backend: string | string[];
}
