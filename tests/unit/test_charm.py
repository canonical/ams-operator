# -*- coding: utf-8 -*-
#
#  Copyright 2024 Canonical Ltd.
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
from ops import BlockedStatus
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


def test_charm_sets_workload_version_on_install(request):
    with patch("ams.snap") as mocked_snap, patch("ams.passwd"), patch("ams.systemd"), patch(
        "ams.SERVICE_DROP_IN_PATH"
    ):
        harness = Harness(AmsOperatorCharm)
        mocked_snap.install_local = MagicMock()
        fake_snap = MagicMock()
        workload_version = "x1"
        fake_snap._snap_client.get_installed_snaps.return_value = [
            {"name": "ams", "version": workload_version}
        ]
        mocked_snap.SnapCache.return_value = fake_snap
        request.addfinalizer(harness.cleanup)
        harness.begin()
        harness.add_resource("ams-snap", "ams.snap")
        harness.charm.on.install.emit()
        assert harness.charm.app._backend._workload_version == workload_version


def test_blocks_on_external_etcd_if_not_embedded(request):
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
        harness.add_resource("ams-snap", "ams.snap")
        harness.begin_with_initial_hooks()
        mocked_server_path.parent.mkdir.assert_called_once()
        mocked_snap.install_local.assert_called_once()
        assert harness.charm.unit.status == BlockedStatus("Waiting for etcd")


def test_can_apply_config_items_to_ams(request):
    with patch("src.charm.AMS"):
        charm_cls = AmsOperatorCharm
        charm_cls.private_ip = "10.0.0.1"
        harness = Harness(charm_cls)
        request.addfinalizer(harness.cleanup)
        harness.add_resource("ams-snap", "ams.snap")
        harness.set_leader(True)
        harness.update_config(
            {
                "use_embedded_etcd": True,
                "config": "images.url=https://dummy.image.io\nimages.auth=custom:auth",
            }
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        harness.charm._snap.apply_service_configuration.assert_called_once()
        assert len(harness.charm._snap.apply_service_configuration.call_args.args[0]) == 2


def test_can_set_location_in_ams(request):
    with patch("src.charm.AMS"):
        charm_cls = AmsOperatorCharm
        charm_cls.private_ip = "10.0.0.1"
        harness = Harness(charm_cls)
        request.addfinalizer(harness.cleanup)
        harness.add_resource("ams-snap", "ams.snap")
        harness.set_leader(True)
        harness.update_config(
            {"use_embedded_etcd": True, "location": "https://custom-endpoint.com"}
        )
        harness.begin()
        harness.charm.on.config_changed.emit()
        harness.charm._snap.set_location.assert_called_once()
