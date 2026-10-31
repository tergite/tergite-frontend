# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""DbStore: what every database backend implements"""
import abc
from typing import Any, List, Optional, Sequence, Type, TypeVar

from .query import Filter
from .schema import Schema
from .update import Returning, Update

T = TypeVar("T", bound=Schema)


class DbStore(abc.ABC):
    """A database behind the Database, which gets only schemas it was created with

    Filters, updates and sorts reach a store already checked against the schema.
    """

    @abc.abstractmethod
    async def setup(self) -> None:
        """Creates what the schemas need, such as tables and indexes; safe to repeat"""

    @abc.abstractmethod
    async def get(self, schema: Type[T], key: Any) -> Optional[T]:
        ...

    @abc.abstractmethod
    async def find(
        self,
        schema: Type[T],
        query_filter: Filter,
        sort: Sequence[str],
        skip: int,
        limit: Optional[int],
    ) -> List[T]:
        ...

    @abc.abstractmethod
    async def count(self, schema: Type[T], query_filter: Filter) -> int:
        ...

    @abc.abstractmethod
    async def find_distinct(
        self, schema: Type[T], field: str, query_filter: Filter
    ) -> List[Any]:
        ...

    @abc.abstractmethod
    async def insert(self, schema: Type[T], record: T) -> T:
        ...

    @abc.abstractmethod
    async def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        ...

    @abc.abstractmethod
    async def update_one(
        self,
        schema: Type[T],
        query_filter: Filter,
        update: Update,
        should_upsert: bool,
        returning: Returning,
    ) -> Optional[T]:
        ...

    @abc.abstractmethod
    async def update_many(
        self, schema: Type[T], query_filter: Filter, update: Update
    ) -> int:
        ...

    @abc.abstractmethod
    async def delete_one(self, schema: Type[T], query_filter: Filter) -> Optional[T]:
        ...

    @abc.abstractmethod
    async def delete_many(self, schema: Type[T], query_filter: Filter) -> int:
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        ...
