import { Box, Heading, Text } from '@chakra-ui/react';
import React from 'react';

export const WACQTInfoCard = ({}) => {
	return (
		<Box bg='white' p='8' rounded='xl' boxShadow='2xl' h='full'>
			<Heading bgGradient='linear(to-l, #389382, #2B8A79)' bgClip='text' fontSize='2xl'>
				WACQT | Wallenberg Centre for Quantum Technology
			</Heading>
			<Text mt={4}>
				Wallenberg Centre for Quantum Technology (WACQT) is a 12 year SEK 1 billion research
				programme that aims to take Swedish research and industry to the forefront of
				quantum technology – a very rapidly expanding area of technology.
			</Text>
		</Box>
	);
};
