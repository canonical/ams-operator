#!/usr/bin/env python3
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

import logging

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def charm_config(snap_risk_level) -> dict:
    cfg = {"use_embedded_etcd": True}
    if snap_risk_level:
        cfg.update(snap_risk_level=snap_risk_level)
    return cfg


@pytest.mark.abort_on_fail
async def test_can_deploy_with_embedded_etcd(
    ops_test: OpsTest, constraints, charm_name, charm_path, charm_config
):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    if not charm_path:
        charm_path = await ops_test.build_charm(".")
    if constraints:
        await ops_test.model.set_constraints(constraints)
    await ops_test.model.deploy(
        charm_path,
        application_name=charm_name,
        config=charm_config,
    )
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[charm_name], status="active", timeout=1000)
