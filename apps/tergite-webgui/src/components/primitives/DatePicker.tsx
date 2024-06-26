import {
	Popover,
	PopoverTrigger,
	Button,
	PopoverContent,
	PopoverArrow,
	Box
} from '@chakra-ui/react';

import React, { useContext, useState } from 'react';
import { DateRange } from 'react-date-range';
import sv from 'react-date-range/dist/locale/';
import 'react-date-range/dist/styles.css'; // main css file
import 'react-date-range/dist/theme/default.css'; // theme css file

import { BackendContext, DateActions } from '../../state/BackendContext';

export default function DatePicker({ refetchFunction }: Props) {
	const [state, dispatch] = useContext(BackendContext);

	const [range, setRange] = useState([
		{
			startDate: state.timeFrom,
			endDate: state.timeTo,
			key: 'selection',
			color: '#38B2AC'
		}
	]);

	const handleChange = (item) => {
		setRange([item.selection]);
		dispatch({ type: DateActions.SET_TIME_FROM, payload: item.selection.startDate });
		dispatch({ type: DateActions.SET_TIME_TO, payload: item.selection.endDate });
	};

	const parseDates = () => {
		return (
			state.timeFrom.toDateString().slice(4, 10) +
			' - ' +
			state.timeTo.toDateString().slice(4, 10)
		);
	};

	return (
		<Box data-cy-date-picker>
			<Popover onClose={() => refetchFunction()} data-cy-date-picker-test>
				<PopoverTrigger>
					<Button
						boxShadow='4px 4px 2px 1px rgba(0, 0, 0, .1)'
						_focus={{ outline: 'none' }}
					>
						Period: {parseDates()}
					</Button>
				</PopoverTrigger>
				<PopoverContent _focus={{ outline: 'none' }}>
					<PopoverArrow />
					<Box>
						{/* @ts-ignore-error */}
						<DateRange
							editableDateInputs={true}
							onChange={(item) => handleChange(item)}
							moveRangeOnFirstSelection={false}
							ranges={range}
							locale={sv}
							maxDate={new Date()}
							weekStartsOn={1}
						/>
					</Box>
				</PopoverContent>
			</Popover>
		</Box>
	);
}

interface Props {
	refetchFunction: () => void;
}
