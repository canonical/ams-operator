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

ETCD_CHARM_NAME = "etcd"
TLS_CHARM_NAME = "easyrsa"
APP_NAMES = [ETCD_CHARM_NAME, TLS_CHARM_NAME]


@pytest.mark.abort_on_fail
async def test_can_relate_to_etcd(ops_test: OpsTest, charm_name, constraints, charm_path):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    if not charm_path:
        charm_path = await ops_test.build_charm(".")
    if constraints:
        await ops_test.model.set_constraints(constraints)
    await asyncio.gather(
        ops_test.model.deploy(charm_path, application_name=charm_name, num_units=1),
        ops_test.model.deploy(
            ETCD_CHARM_NAME,
            application_name=ETCD_CHARM_NAME,
            channel="latest/stable",
            num_units=1,
        ),
        ops_test.model.deploy(
            TLS_CHARM_NAME,
            application_name=TLS_CHARM_NAME,
            channel="latest/stable",
            num_units=1,
        ),
    )

    await asyncio.gather(
        ops_test.model.relate(f"{ETCD_CHARM_NAME}:db", f"{charm_name}:etcd"),
        ops_test.model.relate(f"{TLS_CHARM_NAME}:client", f"{ETCD_CHARM_NAME}:certificates"),
    )
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(
            apps=[*APP_NAMES, charm_name], status="active", timeout=1000
        )
