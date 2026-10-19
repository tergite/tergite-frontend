"""A collection of actions that corresponds to the requests sent"""
from typing import Callable, Any, Coroutine, cast

from utils.exc import BaseMssException
from .dtos import Request, RequestType, CreateProjectMetadata
from ..auth.projects.dtos import Project
from ..auth.projects.routers import prepare_new_project

type Action = Callable[[Request], Coroutine[Any, Any, Any]]
"""An action that can be done given a request"""

class _ActionMismatch(BaseMssException):
    """Exception when the action mismatches the request"""

def do_action(request: Request):
    """Does the action for the given request, ignoring those that don't match

    Args:
        request: the request

    Raises:
        ValueError: No action found for request
    """

async def create_project(request: Request):
    """Creates the project described in the metadata of a create-project request

    Args:
        request: the request sent to create a project

    Raises:
        NotFoundError: no users of emails {emails}
        ConflictError: a project named '{name}' already exists
    """
    if request.type != RequestType.CREATE_PROJECT:
        raise _ActionMismatch(f"expected request {RequestType.CREATE_PROJECT}, got {request.type}")

    metadata = cast(CreateProjectMetadata, request.metadata)
    project = await prepare_new_project(metadata)
    try:
        await project.create()
    except DuplicateKeyError:
        raise ConflictError(f"a project named '{metadata.name}' already exists")

async def _get_user_email_id_map(
            emails: Sequence[str],
    ) -> Dict[str, PydanticObjectId]:
        """Gets the IDs of the users of the given emails, keyed by email

        Args:
            emails: the emails of the users

        Returns:
            the map of email to user ID

        Raises:
            NotFoundError: no users of emails {emails}
        """
        users = await User.find(In(User.email, list(emails))).to_list()
        email_id_map = {user.email: user.id for user in users}
        missing_emails = [email for email in emails if email not in email_id_map]
        if missing_emails:
            raise NotFoundError(f"no users of emails {missing_emails}")

        return email_id_map