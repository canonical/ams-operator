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

import asyncio
import os
import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

INTEGRATOR_CHARM_NAME = "lxd-integrator"


@pytest.mark.abort_on_fail
async def test_can_relate_to_lxd(ops_test: OpsTest, constraints, charm_name, charm_path):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    if not charm_path:
        charm_path = await ops_test.build_charm(".")
    if constraints:
        await ops_test.model.set_constraints(constraints)

    # FIXME: lxd-integrator charm currently has an issue with the platform and
    # series compatibility on different platforms so we modify the deployment to
    # get around it
    deploy_opts = {"base": "ubuntu@20.04"}
    if "2.9" in os.environ["LIBJUJU"]:
        deploy_opts.update(series="jammy")
        deploy_opts.pop("base")

    await asyncio.gather(
        ops_test.model.deploy(
            charm_path,
            application_name=charm_name,
            num_units=1,
            config={"use_embedded_etcd": True},
        ),
        ops_test.model.deploy(
            INTEGRATOR_CHARM_NAME,
            application_name=INTEGRATOR_CHARM_NAME,
            channel="stable",
            trust=True,
            **deploy_opts,
        ),
    )
    async with ops_test.fast_forward():
        await ops_test.model.relate(f"{INTEGRATOR_CHARM_NAME}:api", f"{charm_name}:lxd-cluster"),
        await ops_test.model.wait_for_idle(
            apps=[charm_name, INTEGRATOR_CHARM_NAME], status="active", timeout=1000
        )
