'use client';

import { fetcher, raise } from '@/service/browser';
import Oauth2LoginBtn from './components/Oauth2LoginBtn';
import Page from '@/components/Page';
import useSWRImmutable from 'swr/immutable';
import { type API } from '@/types';
import { useSearchParams, useRouter } from 'next/navigation';
import useSWR from 'swr';

export default function Login() {
	const router = useRouter();
	const nextUrl = useSearchParams().get('next') || '';
	const { data: config, error: configErr } = useSWRImmutable<API.Config>(`/api/config`, fetcher);
	configErr && raise(configErr);

	const { data: user } = useSWR('/api/me', fetcher<API.User>);
	user && nextUrl && router.push(nextUrl);

	return (
		<Page className='flex flex-col gap-2 mx-auto my-auto'>
			{config?.oauth2Providers.map(({ name, logo }) => (
				<Oauth2LoginBtn key={name} provider={name} logo={logo} nextUrl={nextUrl} />
			))}
		</Page>
	);
}
