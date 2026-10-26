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
"""Migrates the MongoDB of the MSS config, from apps/tergite-mss:
`python -m migrations.mongodb upgrade`, or `python -m migrations.mongodb rollback <revision>`
"""
import argparse

from pymongo import MongoClient

import settings
from migrations.mongodb import rollback, upgrade

parser = argparse.ArgumentParser(prog="python -m migrations.mongodb")
commands = parser.add_subparsers(dest="command", required=True)
commands.add_parser("upgrade", help="apply the pending migrations")
rollback_parser = commands.add_parser("rollback", help="undo one migration")
rollback_parser.add_argument("revision")
args = parser.parse_args()

with MongoClient(settings.CONFIG.database.full_url) as client:
    database = client.get_default_database()
    if args.command == "upgrade":
        print(f"MongoDB migrations applied: {upgrade(database) or 'none pending'}")
    else:
        rollback(database, args.revision)
        print(f"MongoDB migration rolled back: {args.revision}")
