# This code is part of Tergite
#
# (C) Copyright Martin Ahindura 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Utilities for use in the puhuri external service"""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from waldur_client import ComponentUsage, WaldurClient

import settings
from utils.date_time import is_in_month
from utils.models import try_parse_record

from .dtos import (
    PuhuriComponent,
    PuhuriFailedRequest,
    PuhuriPlanPeriod,
    PuhuriProjectMetadata,
    PuhuriProviderOffering,
    PuhuriResource,
)
from .exc import ComponentNotFoundError, PlanPeriodNotFoundError


@lru_cache()
def get_client(
    uri: str = settings.CONFIG.puhuri.waldur_api_uri,
    access_token: str = settings.CONFIG.puhuri.waldur_client_token,
) -> WaldurClient:
    """Retrieves the client used to access Puhuri

    This function is currently cached.

    Args:
        uri: the API base URL for the Waldur instance
        access_token: the API token of the user with `service provider manager` role

    Returns:
        the Waldur client instance
    """
    return WaldurClient(uri, access_token=access_token)


async def approve_pending_orders(
    client: WaldurClient,
    provider_uuid: str,
    **kwargs,
) -> Dict[str, Any]:
    """Approves all orders for the given service provider that are in the 'pending-provider' state

    Args:
        client: the WaldurClient
        provider_uuid: the UUID string of the service provider
        kwargs: extra filters for filtering the orders

    Returns:
        dictionary of kwargs used to filter orders.

    Raises:
        WaldurClientException: error making request
        ValueError: no order item found for filter {kwargs}
    """
    loop = asyncio.get_event_loop()

    filter_obj = {
        "state": "pending-provider",
        "provider_uuid": provider_uuid,
        **kwargs,
    }
    order_items = await loop.run_in_executor(None, client.list_orders, filter_obj)
    if len(order_items) == 0:
        raise ValueError(f"no order item found for filter {kwargs}")

    tasks = (
        loop.run_in_executor(
            None, client.marketplace_order_approve_by_provider, order["uuid"]
        )
        for order in order_items
    )
    await asyncio.gather(*tasks)
    return kwargs


async def send_component_usages(
    client: WaldurClient,
    plan_period_uuid: str,
    usages: List[ComponentUsage],
) -> Optional[PuhuriFailedRequest]:
    """Sends the component usages over to Puhuri

    Args:
        client: the Waldur client for accessing Puhuri
        plan_period_uuid: the unique ID for the plan period
        usages: the component usages to send

    Returns:
        PuhuriFailedRequest if the request fails
    """
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            client.create_component_usages,
            plan_period_uuid,
            usages,
        )
    except Exception as exp:
        return PuhuriFailedRequest(
            reason=f"{exp.__class__.__name__}: {exp}",
            method="create_component_usages",
            payload={
                "plan_period_uuid": plan_period_uuid,
                "usages": [asdict(v) for v in usages],
            },
            created_on=datetime.now(tz=timezone.utc),
        )


async def get_project_resources(
    client: WaldurClient,
    provider_uuid: str,
    project_uuid: str,
    state: str = "OK",
) -> List[PuhuriResource]:
    """Gets the resource objects which has the given project_uuid and the given provider_uuid

    Args:
        client: the Waldur client for accessing Puhuri
        provider_uuid: the provider unique ID for this app, as got from Puhuri UI
        project_uuid: the project unique ID for the project
            whose resource are to be reported
        state: the state of the resources to get e.g. "OK", "creating", "terminated" etc.

    Raises:
        WaldurClientException: error making request
        pydantic.error_wrappers.ValidationError: {} validation error for PuhuriResource ...
    """

    loop = asyncio.get_event_loop()
    resource_dicts = await loop.run_in_executor(
        None,
        client.filter_marketplace_resources,
        dict(
            provider_uuid=provider_uuid,
            project_uuid=project_uuid,
            state=state,
        ),
    )

    return [PuhuriResource.model_validate(item) for item in resource_dicts]


async def get_accounting_component(
    client: WaldurClient,
    offering_uuid: str,
    component_type: str,
    cache: Optional[Dict[Tuple[str, str], PuhuriComponent]] = None,
) -> Optional[PuhuriComponent]:
    """Gets the accounting component given the component type and the offering_uuid

    If the caches are provided, it attempts to extract the component
    from the cache if the cache is provided

    Args:
        client: the Waldur client for accessing Puhuri
        offering_uuid: the UUID string of the offering the component belongs to
        component_type: the type of the component
        cache: the dictionary cache that holds components,
            accessible by (offering_uuid, component_type) tuple

    Returns:
        the component or None if the component was malformed

    Raises:
        WaldurClientException: error making request
        pydantic.error_wrappers.ValidationError: {} validation error for PuhuriResource ...
    """
    _cache = cache if isinstance(cache, dict) else {}
    component = _cache.get((offering_uuid, component_type))

    if component is None:
        loop = asyncio.get_event_loop()

        offering = await loop.run_in_executor(
            None,
            client.get_marketplace_provider_offering,
            offering_uuid,
        )

        _cache.update(
            {
                (offering_uuid, v["type"]): try_parse_record(PuhuriComponent, v)
                for v in offering["components"]
            }
        )
        component = _cache[(offering_uuid, component_type)]

    return component


async def get_default_component(
    client: WaldurClient, offering_uuid: str
) -> PuhuriComponent:
    """Gets the default component, given an offering_uuid.

    Here we get the first component that is associated with the given offering

    Args:
        client: the Waldur client for accessing Puhuri
        offering_uuid: the unique ID for the given offering

    Returns:
        the default puhuri component for the givne offering_uuid

    Raises:
        WaldurClientException: error making request
        ComponentNotFoundError: f"offering '{offering_uuid}' has no components"
        pydantic.error_wrappers.ValidationError: {} validation error for PuhuriProviderOffering ...
    """
    loop = asyncio.get_event_loop()
    offering_dict = await loop.run_in_executor(
        None,
        client.get_marketplace_provider_offering,
        offering_uuid,
    )

    offering = PuhuriProviderOffering.model_validate(offering_dict)
    if len(offering.components) == 0:
        raise ComponentNotFoundError(f"offering '{offering_uuid}' has no components")

    return offering.components[0]


async def get_plan_periods(
    client: WaldurClient,
    resource_uuid: str,
    month_year: Optional[Tuple[int, int]] = None,
) -> List[PuhuriPlanPeriod]:
    """Gets the plan periods, given a resource_uuid and month.

    Note that the months start at 1 i.e. January = 1, February = 2, ...

    Args:
        client: the Waldur client for accessing Puhuri
        resource_uuid: the unique ID for the given resource
        month_year: the (month, year) pair that the plan periods should be for; if None, all are returned.

    Returns:
        list of PuhuriPlanPeriod's for the given resource

    Raises:
        WaldurClientException: error making request
        PlanPeriodNotFoundError: f"offering '{offering_uuid}' has no components"
        pydantic.error_wrappers.ValidationError: {} validation error for PuhuriProviderOffering ...
    """
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        client.marketplace_resource_get_plan_periods,
        resource_uuid,
    )

    if isinstance(month_year, tuple):
        results = [v for v in results if is_in_month(month_year, v["start"])]

    if len(results) == 0:
        raise PlanPeriodNotFoundError(
            f"resource '{resource_uuid}' has no plan periods for month {month_year}"
        )

    return [PuhuriPlanPeriod.model_validate(v) for v in results]


def remove_nones(data: Dict[str, Optional[Any]], __new: Any):
    """Replaces None values with the replacement

    Args:
        data: the dictionary whose None values are to be replaced
        __new: the replacement for the None values

    Returns:
        the dictionary with the None values replaced with the replacement
    """
    return {k: v if v is not None else __new for k, v in data.items()}


def extract_project_metadata(
    resources: List[Dict[str, Any]],
) -> List[PuhuriProjectMetadata]:
    """Extracts the project metadata from a list of resources

    A project can contan any number of resources so we need to group the resources
    by project UUID and aggregate any relevant fields like "limits" and "limit_usage"

    Args:
        resources: the list of resource dictionaries

    Returns:
        list of PuhuriProjectMetadata
    """
    results: Dict[str, PuhuriProjectMetadata] = {}

    for resource in resources:
        offering_uuid = resource["offering_uuid"]
        project_uuid = resource["project_uuid"]
        limits = remove_nones(resource["limits"], 0)
        limit_usage = remove_nones(resource["limit_usage"], 0)
        project_meta = PuhuriProjectMetadata(
            uuid=project_uuid,
            limits={offering_uuid: limits},
            limit_usage={offering_uuid: limit_usage},
            resource_uuids=[resource["uuid"]],
        )
        original_meta = results.get(project_uuid, None)

        if isinstance(original_meta, PuhuriProjectMetadata):
            original_limits = original_meta.limits.get(offering_uuid, {})
            project_meta.limits[offering_uuid] = {
                k: v + original_limits.get(k, 0) for k, v in limits.items()
            }

            original_usages = original_meta.limit_usage.get(offering_uuid, {})
            project_meta.limit_usage[offering_uuid] = {
                k: v + original_usages.get(k, 0) for k, v in limit_usage.items()
            }

            project_meta.resource_uuids.extend(original_meta.resource_uuids)

        results[project_uuid] = project_meta

    return list(results.values())


async def get_qpu_seconds(
    client: WaldurClient, metadata: PuhuriProjectMetadata
) -> float:
    """Computes the net QPU seconds the project is left with

    Args:
        client: the Waldur client to access Puhuri
        metadata: the metadata of the project

    Returns:
        the net QPU seconds, i.e. allocated minus used
    """
    net_qpu_seconds = 0
    _components_cache: Dict[Tuple[str, str], PuhuriComponent] = {}

    for offering_uuid, limits in metadata.limits.items():
        limit_usage = metadata.limit_usage.get(offering_uuid, {})

        for comp_type, comp_amount in limits.items():
            component = await get_accounting_component(
                client=client,
                offering_uuid=offering_uuid,
                component_type=comp_type,
                cache=_components_cache,
            )
            if component is None:
                continue

            unit_value = component.measured_unit.to_seconds()
            net_comp_amount = comp_amount - limit_usage.get(comp_type, 0)
            net_qpu_seconds += net_comp_amount * unit_value

    return net_qpu_seconds
