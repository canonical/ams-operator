# -*- coding: utf-8 -*-
#
#  Copyright 2023 Canonical Ltd.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from unittest.mock import MagicMock, patch

import pytest
from ops.testing import Harness

from src.charm import AmsOperatorCharm


@pytest.fixture
def harness(request):
    with patch("ams.snap.SnapCache"):
        harness = Harness(AmsOperatorCharm)
        request.addfinalizer(harness.cleanup)
        harness.begin()
        yield harness


def test_on_install_with_ams_resource(request):
    with patch("ams.snap") as mocked_snap, patch("ams.passwd"), patch("ams.systemd"), patch(
        "ams.SERVICE_DROP_IN_PATH"
    ) as mocked_server_path:
        harness = Harness(AmsOperatorCharm)
        mocked_snap.install_local = MagicMock()
        fake_snap = MagicMock()
        fake_snap._snap_client.get_installed_snaps.return_value = [
            {"name": "ams", "version": "x1"}
        ]
        mocked_snap.SnapCache.return_value = fake_snap
        request.addfinalizer(harness.cleanup)
        harness.begin()
        harness.add_resource("ams-snap", "ams.snap")
        harness.charm.on.install.emit()
        mocked_server_path.parent.mkdir.assert_called_once()
        mocked_snap.install_local.assert_called_once()
