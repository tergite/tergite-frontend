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
"""MongoDB's migrations: each JSON here holds the updates that bring MongoDB's documents
to the Alembic revision it is named after, and back

MSS's start script applies the pending ones, in the order of Alembic's revisions;
`apply.js` applies one by hand with mongosh. Both record what they apply in
`mongodb_migrations`, and both bypass document validation, as the validator in place
belongs to the MSS before the change.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from alembic.config import Config
from alembic.script import ScriptDirectory
from bson import json_util
from pymongo.database import Database

RECORDS_COLLECTION = "mongodb_migrations"

_MIGRATIONS_DIR = Path(__file__).parent
_APP_ROOT = _MIGRATIONS_DIR.parent.parent


def upgrade(database: Database) -> List[str]:
    """Applies the migrations not yet recorded, oldest first

    Returns:
        the revisions applied

    Raises:
        ValueError: a migration is named after no Alembic revision
    """
    files = _get_migration_files()
    revisions = _get_revisions()
    unknown = set(files) - set(revisions)
    if unknown:
        raise ValueError(f"no Alembic revision for the MongoDB migrations {unknown}")

    applied = set(database[RECORDS_COLLECTION].distinct("_id"))
    pending = [rev for rev in revisions if rev in files and rev not in applied]
    for revision in pending:
        _apply(database, files[revision], "upgrade")
        database[RECORDS_COLLECTION].update_one(
            {"_id": revision},
            {"$set": {"applied_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
    return pending


def rollback(database: Database, revision: str) -> None:
    """Undoes the migration of the revision

    Raises:
        KeyError: no migration is named after the revision
    """
    _apply(database, _get_migration_files()[revision], "rollback")
    database[RECORDS_COLLECTION].delete_one({"_id": revision})


def _get_migration_files() -> Dict[str, Path]:
    return {path.name.split("_")[0]: path for path in _MIGRATIONS_DIR.glob("*.json")}


def _get_revisions() -> List[str]:
    """Alembic's revisions, oldest first"""
    config = Config(str(_APP_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_APP_ROOT / "migrations"))
    scripts = list(ScriptDirectory.from_config(config).walk_revisions())
    return [script.revision for script in reversed(scripts)]


def _apply(database: Database, path: Path, direction: str) -> None:
    migration = json_util.loads(path.read_text())
    for step in migration[direction]:
        database[step["collection"]].update_many(
            step["filter"], step["update"], bypass_document_validation=True
        )
