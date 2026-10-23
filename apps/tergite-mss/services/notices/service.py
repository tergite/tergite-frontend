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
#
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from beanie import PydanticObjectId
from loguru import logger
from pydantic import BaseModel

from libs.storage import (
    ALL,
    AddToSet,
    And,
    Database,
    Eq,
    Filter,
    In,
    Ne,
    NotIn,
    Or,
    Page,
    Pull,
    Range,
    Set,
    SetOnInsert,
    Sort,
    Update,
)
from services.external.email.service import Emailer
from utils.config import NoticesConfig
from utils.date_time import get_current_timestamp, get_utc_now
from utils.exc import NotFoundError

from .dtos import (
    BaseNoticeContext,
    CustomNoticeCreate,
    EmailStatus,
    Notice,
    NoticePreferences,
    NoticeTemplate,
    NoticeType,
    NoticeTypeId,
    ProjectRequestContext,
    RefType,
)
from .emails import (
    get_email_preferences_map,
    get_pending_email_batches,
    process_email_batch_results,
)

if TYPE_CHECKING:
    from services.auth import User

# on_startup replaces these with what the app is configured with
_conf = NoticesConfig()
_is_email_enabled = False
# FIXME: create_system_notice and clear_notices_by_reference use this Database because
#   their callers in auth and requests have none to pass yet; they take one as an
#   argument once those callers do (step 5)
_database: Optional[Database] = None
_IS_BROADCAST = Eq("type", NoticeType.CUSTOM_BROADCAST.id)
_IS_NOT_BROADCAST = Ne("type", NoticeType.CUSTOM_BROADCAST.id)


async def set_read_status(
    database: Database, pk: str, user_id: str, is_read: bool
) -> Notice:
    """Sets the read status of the notice for the given user

    Args:
        database: the database where the notices are stored
        pk: the id of the notice
        user_id: the ID of the user to dismiss the notice for
        is_read: whether the notice was read or not

    Returns:
        the updated notice

    Raises:
        NotFoundError: if the notice does not exist or is not addressed to the user
    """
    user_id = str(user_id)
    where = And(Eq("id", str(pk)), In("user_id", [user_id, None]))
    for kind, changes in _build_read_status_changes(user_id, is_read=is_read):
        notice = await database.update_one(
            Notice, where=And(where, kind), changes=changes
        )
        if notice is not None:
            return notice
    raise NotFoundError(f"notice of ID '{pk}' not found")


async def set_read_status_many(
    database: Database,
    user_id: str,
    is_read: bool,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    types: Optional[Sequence[NoticeTypeId]] = None,
) -> int:
    """Marks many of the user's notices read or unread

    Args:
        database: the database where the notices are stored
        user_id: the recipient whose notices are to be updated
        is_read: True to mark read, False to mark unread
        min_start_utc: the minimum UTC timestamp that the notice should start
        max_start_utc: the maximum UTC timestamp that the notice should start
        min_expires_utc: the minimum UTC timestamp that the notice should expire
        max_expires_utc: the maximum UTC timestamp that the notice should expire
        types: the notice types to filter by; default = None i.e. any

    Returns:
        the number of notices updated
    """
    user_id = str(user_id)
    where = build_filter(
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        should_include_dismissed=True,
        types=types,
        is_read=not is_read,
    )
    count = 0
    for kind, changes in _build_read_status_changes(user_id, is_read=is_read):
        count += await database.update_many(Notice, And(where, kind), changes)
    return count


async def clear_notices_by_reference(ref_type_ids_map: Dict[RefType, List[str]]) -> int:
    """Marks read every unread notice associated with the given reference ids per type

    This is useful in bulk clearing notices that no longer have any consequence,
    without having users dismiss them manually. An example is a user request to create
    a project. If the system admin created that project then there would be no need
    for that admin to go clear all the notices manually.

    Args:
        ref_type_ids_map: mapping of reference types and the reference IDs

    Returns:
        the number of notices updated
    """
    if not ref_type_ids_map:
        return 0

    now = get_utc_now()
    timestamp = get_current_timestamp()
    where = And(
        Eq("read_at", None),
        Or(
            *(
                And(In("ref_id", [str(v) for v in ref_ids]), Eq("ref_type", ref_type))
                for ref_type, ref_ids in ref_type_ids_map.items()
            )
        ),
        Or(Eq("expires_at", None), Range("expires_at", gte=now)),
    )
    expire_now = [Set("updated_at", timestamp), Set("expires_at", now)]
    count = await _database.update_many(Notice, And(where, _IS_BROADCAST), expire_now)

    # a recipient's notice is read when it holds its own user_id in dismissed_by
    user_ids = await _database.find_distinct(
        Notice, "user_id", where=And(where, _IS_NOT_BROADCAST)
    )
    for user_id in user_ids:
        count += await _database.update_many(
            Notice,
            And(where, _IS_NOT_BROADCAST, Eq("user_id", user_id)),
            [AddToSet("dismissed_by", user_id), Set("read_at", timestamp), *expire_now],
        )
    return count


async def delete_notice(database: Database, pk: str) -> Notice:
    """Deletes the notice

    Raises:
        NotFoundError: if the notice does not exist
    """
    notice = await database.delete_one(Notice, where=Eq("id", str(pk)))
    if notice is None:
        raise NotFoundError(f"notice of ID '{pk}' not found")
    return notice


async def publish_custom_notice(
    database: Database, current_user_id: str, payload: CustomNoticeCreate
) -> List[Notice]:
    """Creates the custom notice, one per target user, or one broadcast

    Args:
        database: the database where the notices are stored
        current_user_id: the ID of the current user
        payload: the notice payload

    Returns:
        the created notices
    """
    notices = await payload.to_documents(database, created_by=str(current_user_id))
    return await database.insert_many(Notice, notices)


async def create_system_notice(
    user_ids: Sequence[str],
    notice_type: NoticeTypeId,
    context: Optional[BaseNoticeContext] = None,
    ref_type: Optional[RefType] = None,
    ref_id: Optional[str] = None,
    **kwargs,
) -> List[Notice]:
    """Creates a system notice for the given users.

    Never raises: a notification is a side effect of some other operation, and failing to
    deliver one must not fail the operation that triggered it.

    Args:
        user_ids: the recipients; one document is written per user
        notice_type: the notice type, which selects the copy and the channel policy
        context: values for generating the notice content; a project request context
            without a project name gets the name of the project of its project_id
        ref_type: the reference type that is associated with this notice, e.g. a user_request
        ref_id: the unique identifier of the reference in the collection of the given ref_type

    Returns:
        the created notices, or an empty list if none were created
    """
    if len(user_ids) == 0:
        return []

    try:
        user_ids = [str(v) for v in user_ids]
        context = await _with_project_name(context)
        template = await _database.get(NoticeTemplate, notice_type)
        email_prefs_map = await get_email_preferences_map(
            _database, notice_type, user_ids=user_ids
        )
        email_status_map = {
            user_id: (
                EmailStatus.PENDING
                if _is_email_enabled and email_prefs_map.get(user_id, True)
                else EmailStatus.NOT_APPLICABLE
            )
            for user_id in user_ids
        }
        expires_at = get_utc_now() + timedelta(_conf.retention_days)
        records = [
            Notice.from_template(
                template=template,
                context=context,
                user_id=user_id,
                type=notice_type,
                ref_type=ref_type,
                ref_id=None if ref_id is None else str(ref_id),
                email_status=email_status_map[user_id],
                expires_at=expires_at,
            )
            for user_id in user_ids
        ]
        return await _database.insert_many(Notice, records)
    except Exception:
        logger.exception(f"failed to emit {notice_type} notification")
        return []


async def find_many(
    database: Database,
    where: Filter = ALL,
    sort: Sequence[Sort] = (),
    page: Page = Page(),
) -> List[Notice]:
    """Gets the notices that match the filter, which build_filter makes

    Raises:
        ValidationError: final results are not valid Notice objects
    """
    return await database.find(Notice, where=where, sort=sort, page=page)


async def count_many(
    database: Database,
    requester: "User",
    user_id: Optional[str] = None,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    should_include_dismissed: bool = False,
    types: Optional[Sequence[NoticeTypeId]] = None,
    is_read: Optional[bool] = None,
) -> int:
    """Gets the number of notices that match the given constraints, as build_filter takes them

    Args:
        database: the database where the notices are stored
        requester: the user asking; anyone but a superuser counts only their own notices
        user_id: the ID of the user whose notices we might be interested in
        min_start_utc: the minimum UTC timestamp that the notice should start
        max_start_utc: the maximum UTC timestamp that the notice should start
        min_expires_utc: the minimum UTC timestamp that the notice should expire
        max_expires_utc: the maximum UTC timestamp that the notice should expire
        should_include_dismissed: whether to include dismissed notices; defaults to False
        types: the notice types to filter by; default = None i.e. any
        is_read: whether to have notices that are read or not; defaults to None
    """
    if not requester.is_superuser:
        user_id = requester.id
    where = build_filter(
        user_id=user_id,
        min_start_utc=min_start_utc,
        max_start_utc=max_start_utc,
        min_expires_utc=min_expires_utc,
        max_expires_utc=max_expires_utc,
        should_include_dismissed=should_include_dismissed,
        types=types,
        is_read=is_read,
    )
    return await database.count(Notice, where=where)


async def get_one(database: Database, pk: str) -> Notice:
    """Gets the notice of the given pk

    Raises:
        NotFoundError: no matches for {_id: '<pk>'}
    """
    notice = await database.get(Notice, str(pk))
    if notice is None:
        raise NotFoundError(f"no matches for '{ {'_id': str(pk)} }'")
    return notice


async def get_email_preferences(
    database: Database, user_id: str
) -> Dict[NoticeTypeId, bool]:
    """The user's effective preferences, with defaults filled in for every type"""
    record = await database.get(NoticePreferences, str(user_id))
    prefs_in_db = record.email_prefs if record is not None else {}
    return _with_default_email_preferences(prefs_in_db)


async def set_email_preferences(
    database: Database, user_id: str, prefs: Dict[NoticeTypeId, bool]
) -> Dict[NoticeTypeId, bool]:
    """Applies a partial preference update

    Returns:
        the user's full effective preferences after the update
    """
    user_id = str(user_id)
    record = await database.get(NoticePreferences, user_id)
    current = record.email_prefs if record is not None else {}
    current.update(prefs)
    timestamp = get_current_timestamp()
    await database.update_one(
        NoticePreferences,
        where=Eq("user_id", user_id),
        changes=[
            Set("email_prefs", current),
            Set("updated_at", timestamp),
            SetOnInsert("created_at", timestamp),
        ],
        should_upsert=True,
    )
    return _with_default_email_preferences(current)


def build_filter(
    user_id: Optional[str] = None,
    min_start_utc: Optional[datetime] = None,
    max_start_utc: Optional[datetime] = None,
    min_expires_utc: Optional[datetime] = None,
    max_expires_utc: Optional[datetime] = None,
    should_include_dismissed: bool = False,
    types: Optional[Sequence[NoticeTypeId]] = None,
    is_read: Optional[bool] = None,
) -> Filter:
    """Builds the filter of the notices that fit the given constraints

    Args:
        user_id: the user whose notices, direct or broadcast, are wanted
        min_start_utc: the minimum UTC timestamp that the notice should start
        max_start_utc: the maximum UTC timestamp that the notice should start
        min_expires_utc: the minimum UTC timestamp that the notice should expire
        max_expires_utc: the maximum UTC timestamp that the notice should expire
        should_include_dismissed: whether to include notices the user dismissed
        types: the notice types to match; default = None i.e. any
        is_read: whether the notices should be read; default = None i.e. either
    """
    user_id = None if user_id is None else str(user_id)
    filters: List[Filter] = []
    if user_id:
        if not should_include_dismissed:
            filters.append(NotIn("dismissed_by", [user_id]))
        # either broadcast notices or those sent directly to user
        filters.append(In("user_id", [user_id, None]))
    if min_start_utc or max_start_utc:
        filters.append(Range("starts_at", gte=min_start_utc, lte=max_start_utc))
    if min_expires_utc or max_expires_utc:
        filters.append(Range("expires_at", gte=min_expires_utc, lte=max_expires_utc))
    if types:
        filters.append(In("type", list(types)))
    if is_read is False:
        filters.append(NotIn("dismissed_by", [user_id]))
    elif is_read:
        filters.append(In("dismissed_by", [user_id]))
    return And(*filters)


async def on_startup(
    database: Database, emailer: Optional[Emailer], conf: NoticesConfig
) -> None:
    """Runs init operations when the application is starting up

    Args:
        database: the database where the notices are stored
        emailer: the emailer instance that sends emails; None if email is not configured
        conf: the notices configuration
    """
    global _conf, _is_email_enabled, _database
    _conf = conf
    _is_email_enabled = emailer is not None
    _database = database

    await _init_notice_templates_in_db(database)

    if emailer is None:
        return

    batch_generator = get_pending_email_batches(
        database,
        batch_size=50,
        dashboard_url=conf.dashboard_url,
        app_name=conf.app_name,
        max_attempts=conf.email_retry_limit,
    )
    emailer.register_batch_schedule(
        "notices",
        interval=conf.email_sweep_interval,
        batch_generator=batch_generator,
        batch_callback=partial(process_email_batch_results, database),
        ignore_errors=True,
    )


async def _init_notice_templates_in_db(database: Database) -> None:
    """Initializes the notice templates in the database with the default templates"""
    existing_types = set(await database.find_distinct(NoticeTemplate, "type"))
    new_records = [
        NoticeTemplate.from_notice_type(v)
        for v in NoticeType
        if v.id not in existing_types
    ]
    if new_records:
        await database.insert_many(NoticeTemplate, new_records)
        logger.info(f"Initialized {len(new_records)} new notice template(s) in db.")


def _build_read_status_changes(
    user_id: str, is_read: bool
) -> List[Tuple[Filter, List[Update]]]:
    """Gets, per kind of notice, the changes that mark it read or unread for the user

    Broadcast notices are shared by many users, so their read state lives in
    'dismissed_by' alone and 'read_at' stays None.
    """
    now = get_current_timestamp()
    member_change = AddToSet if is_read else Pull
    changes = [member_change("dismissed_by", user_id), Set("updated_at", now)]
    return [
        (_IS_BROADCAST, changes),
        (_IS_NOT_BROADCAST, [*changes, Set("read_at", now if is_read else None)]),
    ]


def _with_default_email_preferences(
    prefs: Dict[NoticeTypeId, bool]
) -> Dict[NoticeTypeId, bool]:
    """Fills in the default email preference for every notice type missing in prefs"""
    return {v.id: prefs.get(v.id, True) for v in NoticeType}


async def _with_project_name(
    context: Optional[BaseNoticeContext],
) -> Optional[BaseNoticeContext]:
    """Fills in the project name of a project request context that has only a project_id

    Deleted projects are searched too, as approving a close-project request deletes
    the project before its requester is told.
    """
    is_name_missing = (
        isinstance(context, ProjectRequestContext)
        and not context.project_name
        and PydanticObjectId.is_valid(context.project_id)
    )
    if not is_name_missing:
        return context

    # imported here to avoid a circular import, as the auth service imports this one
    from services.auth.projects.dtos import DeletedProject, Project

    project_id = PydanticObjectId(context.project_id)
    for document_cls in (Project, DeletedProject):
        project = await document_cls.find_one(
            document_cls.id == project_id, projection_model=_ProjectName
        )
        if project is not None:
            return context.model_copy(update={"project_name": project.name})
    return context


class _ProjectName(BaseModel):
    """A project with only its name"""

    name: str
