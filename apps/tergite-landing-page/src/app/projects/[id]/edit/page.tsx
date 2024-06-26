'use client';

import Page, { HeaderBtn, PageHeader, PageMain } from '@/components/Page';
import { fetcher, raise, updater } from '@/service/browser';
import { API } from '@/types';
import useSWRImmutable from 'swr/immutable';
import useSWRMutation from 'swr/mutation';
import { MouseEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Form, { CustomInputEvent, MultiInput, Input } from '@/components/Form';
import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';

export default function EditProject() {
	const { id } = useParams();
	const router = useRouter();
	const [project, setProject] = useState<API.ProjectPartial>();

	const configGetter = useSWRImmutable<API.Config>(`/api/config`, fetcher);
	configGetter.error && raise(configGetter.error);

	const swrKey = configGetter.data ? `${configGetter.data.baseUrl}/auth/projects/${id}` : null;
	const mutator = useSWRMutation(swrKey, updater<API.ProjectPartial>);
	mutator.error && raise(mutator.error);

	const getter = useSWR<API.Project>(swrKey, fetcher);
	getter.error && raise(getter.error);

	const { isMutating } = mutator;

	const handleSubmit = useCallback(
		(ev: MouseEvent<HTMLButtonElement>) => {
			ev.preventDefault();
			mutator
				.trigger(project)
				.then(() => {
					router.push(`/projects/${id}`);
				})
				.catch(console.error);
		},
		[mutator, id, router, project]
	);

	const handleInputChange = useCallback(
		(ev: CustomInputEvent<string | number | (string | number)[]>) => {
			ev.preventDefault();
			const { name, value } = ev.target;
			setProject((prevObj) => ({ ...(prevObj || {}), [name]: value }));
		},
		[setProject]
	);

	useEffect(() => {
		if (getter.data && project === undefined) {
			setProject({ ...getter.data });
		}
	}, [setProject, project, getter.data]);

	return (
		<Page className='h-full w-full'>
			<Form className='w-full h-full'>
				<PageHeader heading={`Editing Project '${project?.ext_id}'`}>
					<HeaderBtn
						type='button'
						text='Save'
						onClick={handleSubmit}
						disabled={isMutating}
						isLoading={isMutating}
					/>
				</PageHeader>

				<PageMain className='py-10 px-5'>
					{project && (
						<>
							<Input
								type='text'
								value={project.ext_id}
								label='External ID'
								name='ext_id'
								disabled
								required
								onChange={handleInputChange}
							/>

							<Input
								label='QPU Seconds'
								value={project.qpu_seconds}
								type='number'
								name='qpu_seconds'
								required
								onChange={handleInputChange}
							/>

							<MultiInput
								label='User Emails'
								value={project.user_emails}
								name='user_emails'
								type='email'
								required
								onChange={handleInputChange}
							/>
						</>
					)}
				</PageMain>
			</Form>
		</Page>
	);
}
