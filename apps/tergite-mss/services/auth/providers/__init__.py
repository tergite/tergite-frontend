from typing import Any, Dict, List, Optional

import settings
from utils.exc import NotFoundError

from .dtos import AuthProvider, AuthProviderRead

_ALL_AUTH_PROVIDERS = [
    AuthProvider(
        name=client.name,
        email_domain=client.email_domain,
        url=client.redirect_url.replace("/callback", "/auto-authorize"),
    )
    for client in settings.CONFIG.auth.clients
]


def get_many(
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    skip: int = 0,
    sort: List[str] = (),
) -> List[AuthProviderRead]:
    """Gets the auth providers that correspond to the given email domain

    Args:
        filters: the key-value items to match when getting the providers
        limit: the number of results to return: default = None meaning all of them
        skip: the number of records to skip; default = 0
        sort: the fields to sort by, prefixing any with a '-' means descending; default = ()

    Returns:
        list of matched auth providers

    Raises:
         NotFoundError: no matches for {filters}
    """
    if limit is None:
        limit = len(_ALL_AUTH_PROVIDERS)

    data = _filter_by_equality(_ALL_AUTH_PROVIDERS, filters=filters)
    if len(data) == 0:
        raise NotFoundError(f"Not Found")

    data = _order_by_many(data, fields=sort)
    sliced_data = data[skip : skip + limit]
    return [item.as_public_view() for item in sliced_data]


def _filter_by_equality(
    records: List[AuthProvider], filters: Optional[Dict[str, Any]]
) -> List[AuthProvider]:
    """Filters the records that match the given filters

    It simply checks that the matched record has the properties in the filters dict

    Args:
        records: the data to filter
        filters: the properties that matched dicts should have

    Returns:
        the records that match the given filters
    """
    if filters is None:
        return [*records]

    return [
        item
        for item in records
        if all([getattr(item, k, None) == v for k, v in filters.items()])
    ]


def _order_by_many(data: List[AuthProvider], fields: List[str]) -> List[AuthProvider]:
    """Orders the data by many fields

    Args:
        data: the list of records to sort
        fields: the fields to order by, if a field starts with "-" then order is descending

    Returns:
        the ordered list of records
    """

    def get_key(item) -> tuple:
        return tuple(
            (
                getattr(item, field, None)
                if not field.startswith("-")
                else _to_hash(getattr(item, field[1:], None), negated=True)
            )
            for field in fields
        )

    return sorted(data, key=get_key)


def _to_hash(value: Any, negated: bool = False) -> tuple[int, ...] | int | float | None:
    """Converts a value to comparable hash that is negated if negated is True

    Args:
        value: the value whose comparable hash is to be obtained
        negated: whether to negate the hash to get a descending value or not

    Returns:
        the comparable hash
    """
    multiplier = 1 if not negated else -1
    if isinstance(value, str):
        return tuple(multiplier * ord(char) for char in value)
    if isinstance(value, (int, float)):
        return multiplier * value
    if value is None:
        return None
    raise TypeError(f"type {type(value)} cannot be hashed for ordering")
