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

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

TEST_APP_CHARM_PATH = "tests/integration/application-charm"
TEST_APP_CHARM_NAME = 'ams-api-tester'

@pytest.mark.abort_on_fail
async def test_can_relate_to_client_charms(
    ops_test: OpsTest, ams_snap, charm_name, constraints, charm_path
):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    if not charm_path:
        charm_path = await ops_test.build_charm(".")
    if constraints:
        await ops_test.model.set_constraints(constraints)
    client_charm_path = await ops_test.build_charm(TEST_APP_CHARM_PATH)
    ams = await ops_test.model.deploy(
            charm_path, application_name=charm_name, num_units=1, resources={"ams-snap": "ams.snap"}, config={'use_embedded_etcd': True}
    )
    with open(ams_snap, "rb") as res:
        ams.attach_resource("ams-snap", "ams.snap", res)
    await asyncio.gather(
        ops_test.model.deploy(
            client_charm_path,
            application_name=TEST_APP_CHARM_NAME,
            channel="latest/stable",
            num_units=1,
        ),
    )
    await ops_test.model.relate(f"{TEST_APP_CHARM_NAME}:client", f"{charm_name}:rest-api")
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=[TEST_APP_CHARM_NAME, charm_name], status="active", timeout=1000
        )
