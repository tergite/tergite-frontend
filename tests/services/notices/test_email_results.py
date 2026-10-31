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

from services.external.email import EmailResult
from services.notices.emails import _partition_results


def test_results_split_into_sent_failed_and_retried():
    ids = _partition_results(
        [
            EmailResult(ref_id="sent"),
            EmailResult(error=OSError(), ref_id="failed", can_retry=False),
            EmailResult(error=OSError(), ref_id="retried"),
        ]
    )

    assert (ids.sent, ids.failed, ids.retried) == (["sent"], ["failed"], ["retried"])
