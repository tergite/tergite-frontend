import { Icon, Input, InputGroup, InputLeftElement } from '@chakra-ui/react';
import React, { memo } from 'react';
import { MdOutlineSearch } from 'react-icons/md';

const SearchBar = ({ search, setSearch }: Props) => {
	return (
		<InputGroup w='md'>
			<InputLeftElement pointerEvents='none'>
				<Icon as={MdOutlineSearch} />
			</InputLeftElement>
			<Input
				type='text'
				placeholder='Search'
				backgroundColor='#FFFFFF'
				onChange={(e) => setSearch(e.target.value)}
				value={search}
				data-cy-devices-search
			/>
		</InputGroup>
	);
};

export default memo(SearchBar);

interface Props {
	search: string;
	setSearch: React.Dispatch<React.SetStateAction<string>>;
}
