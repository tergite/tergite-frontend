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
"""MongoDB's migrations apply once, in Alembic's order, and roll back"""

import shutil

import pytest
from pymongo import MongoClient

import migrations.mongodb
from migrations.mongodb import RECORDS_COLLECTION, rollback, upgrade
from tests._utils.env import TEST_MONGODB_URL

_SEVERITY_REVISION = "b109440758fe"
_CONTEXT_CLASS_REVISION = "01f3a918b5dd"


@pytest.fixture
def database():
    with MongoClient(TEST_MONGODB_URL) as client:
        client.drop_database("mss_mongodb_migrations")
        yield client["mss_mongodb_migrations"]
        client.drop_database("mss_mongodb_migrations")


def test_upgrade_applies_each_pending_migration_once(database):
    assert _SEVERITY_REVISION in upgrade(database)
    assert upgrade(database) == []
    assert database[RECORDS_COLLECTION].count_documents({}) == len(
        list(migrations.mongodb._MIGRATIONS_DIR.glob("*.json"))
    )


def test_notice_severities_become_numbers_and_back_past_each_validator(database):
    database.create_collection(
        "notices", validator=_get_severity_validator(["info", "warning", "critical"])
    )
    database.notices.insert_many(
        [
            {"title": "c", "severity": "critical", "severity_number": 1},
            {"title": "w", "severity": "warning"},
            {"title": "i", "severity": "info"},
        ]
    )
    database.notice_templates.insert_one({"type": "custom", "severity": "warning"})

    upgrade(database)

    assert _get_severities(database.notices) == {"c": 1, "w": 2, "i": 3}
    assert database.notices.count_documents({"severity_number": {"$exists": True}}) == 0
    assert database.notice_templates.find_one()["severity"] == 2

    database.command("collMod", "notices", validator=_get_severity_validator([1, 2, 3]))
    rollback(database, _SEVERITY_REVISION)

    assert _get_severities(database.notices) == {
        "c": "critical",
        "w": "warning",
        "i": "info",
    }
    assert database.notice_templates.find_one()["severity"] == "warning"
    assert (
        database[RECORDS_COLLECTION].count_documents({"_id": _SEVERITY_REVISION}) == 0
    )


def test_notice_templates_lose_their_context_class(database):
    database.notice_templates.insert_one(
        {
            "type": "custom",
            "context_cls_path": "services.notices.dtos.CustomNoticeContext",
        }
    )

    assert _CONTEXT_CLASS_REVISION in upgrade(database)

    assert "context_cls_path" not in database.notice_templates.find_one()


def test_upgrade_refuses_a_migration_named_after_no_alembic_revision(
    database, tmp_path, monkeypatch
):
    for path in migrations.mongodb._MIGRATIONS_DIR.glob("*.json"):
        shutil.copy(path, tmp_path)
    (tmp_path / "0123456789ab_stray.json").write_text('{"upgrade": [], "rollback": []}')
    monkeypatch.setattr(migrations.mongodb, "_MIGRATIONS_DIR", tmp_path)

    with pytest.raises(ValueError, match="0123456789ab"):
        upgrade(database)


def _get_severity_validator(allowed: list) -> dict:
    return {"$jsonSchema": {"properties": {"severity": {"enum": allowed}}}}


def _get_severities(collection) -> dict:
    return {doc["title"]: doc["severity"] for doc in collection.find()}
