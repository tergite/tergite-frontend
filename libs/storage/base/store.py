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
        """Gets the unexpired record of the given key

        Args:
            schema: the schema of the record
            key: the value of the schema's key field

        Returns:
            the record, or None if there is none
        """
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
        """Finds the unexpired records that match the filter, in the sort's order

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it
            sort: the fields to sort by; a leading '-' sorts descending
            skip: the number of matched records to skip
            limit: the most records to return; None returns all

        Returns:
            the matched records
        """
        ...

    @abc.abstractmethod
    async def count(self, schema: Type[T], query_filter: Filter) -> int:
        """Counts the unexpired records that match the filter

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the number of matched records
        """
        ...

    @abc.abstractmethod
    async def find_distinct(
        self, schema: Type[T], field: str, query_filter: Filter
    ) -> List[Any]:
        """Gets the different values the field holds in the matched records

        Args:
            schema: the schema of the records
            field: the field, dotted for a nested one
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the distinct values
        """
        ...

    @abc.abstractmethod
    async def insert(self, schema: Type[T], record: T) -> T:
        """Inserts the record

        Args:
            schema: the schema of the record
            record: the record to insert

        Returns:
            the inserted record

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        ...

    @abc.abstractmethod
    async def insert_many(self, schema: Type[T], records: Sequence[T]) -> List[T]:
        """Inserts the records

        Args:
            schema: the schema of the records
            records: the records to insert

        Returns:
            the inserted records

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
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
        """Updates the first matched record

        Args:
            schema: the schema of the record
            query_filter: the filter, as `Database.find` takes it
            update: the update, as `Database.update_one` takes it
            should_upsert: whether to create the record if none matched
            returning: whether to return the record as it was before or after the update

        Returns:
            the record before or after the update, or None if none matched and none was
            upserted

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        ...

    @abc.abstractmethod
    async def update_many(
        self, schema: Type[T], query_filter: Filter, update: Update
    ) -> int:
        """Updates every matched record

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it
            update: the update, as `Database.update_one` takes it

        Returns:
            the number of records changed

        Raises:
            DuplicateKeyError: a unique field's value is taken
        """
        ...

    @abc.abstractmethod
    async def delete_one(self, schema: Type[T], query_filter: Filter) -> Optional[T]:
        """Deletes the first matched record

        Args:
            schema: the schema of the record
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the deleted record, or None if none matched
        """
        ...

    @abc.abstractmethod
    async def delete_many(self, schema: Type[T], query_filter: Filter) -> int:
        """Deletes every matched record

        Args:
            schema: the schema of the records
            query_filter: the filter, as `Database.find` takes it

        Returns:
            the number of records deleted
        """
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """Closes the connections to the database"""
        ...
