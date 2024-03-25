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
from unittest.mock import PropertyMock
import pytest

from ops import BlockedStatus
from ops.testing import Harness
from ams import SNAP_DEFAULT_RISK

from src.charm import AmsOperatorCharm


@pytest.fixture
def charm():
    charm_cls = AmsOperatorCharm
    charm_cls.private_ip = "10.0.0.1"
    return charm_cls


def test_charm_installs_specific_revision(request, mocked_ams, charm, current_version):
    harness = Harness(charm)
    harness.update_config({"snap_revision": "567"})
    request.addfinalizer(harness.cleanup)
    harness.begin()
    harness.charm.on.install.emit()
    harness.charm.ams.install.assert_called_with(
        channel=f"{current_version}/{SNAP_DEFAULT_RISK}", revision="567"
    )


def test_charm_sets_workload_version_on_install(request, mocked_ams, charm):
    workload_version = "1.21"
    type(mocked_ams).version = PropertyMock(return_value=workload_version)
    harness = Harness(charm)
    request.addfinalizer(harness.cleanup)
    harness.begin()
    harness.charm.on.install.emit()
    assert harness.charm.app._backend._workload_version == workload_version


def test_blocks_on_external_etcd_if_not_embedded(request, mocked_ams, charm):
    harness = Harness(charm)
    request.addfinalizer(harness.cleanup)
    harness.begin_with_initial_hooks()
    assert harness.charm.unit.status == BlockedStatus("Waiting for etcd")


def test_can_apply_config_items_to_ams(request, mocked_ams, charm):
    harness = Harness(charm)
    request.addfinalizer(harness.cleanup)
    harness.set_leader(True)
    harness.update_config(
        {
            "use_embedded_etcd": True,
            "config": "images.url=https://dummy.image.io\nimages.auth=custom:auth",
        }
    )
    harness.begin()
    harness.charm.on.config_changed.emit()
    harness.charm.ams.apply_service_configuration.assert_called_once()
    assert len(harness.charm.ams.apply_service_configuration.call_args.args[0]) == 2


def test_can_set_location_in_ams(request, mocked_ams, charm):
    harness = Harness(charm)
    request.addfinalizer(harness.cleanup)
    harness.set_leader(True)
    harness.update_config({"use_embedded_etcd": True, "location": "https://custom-endpoint.com"})
    harness.begin()
    harness.charm.on.config_changed.emit()
    harness.charm.ams.set_location.assert_called_once()
