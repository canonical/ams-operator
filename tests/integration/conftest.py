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
from pathlib import Path

import pytest
import yaml


def pytest_addoption(parser):
    parser.addoption("--ams-snap", required=True, action="store", help="Snap resource for ams")
    parser.addoption("--constraints", default="", action="store", help="Model constraints")
    parser.addoption("--charm", default="", action="store", help="Path to a built charm")


@pytest.fixture
def charm_name():
    metadata = yaml.safe_load(Path("./metadata.yaml").read_text())
    return metadata["name"]


@pytest.fixture
def constraints(request) -> dict:
    constraints = request.config.getoption("--constraints")
    cts = {}
    for constraint in constraints.split(" "):
        k, v = constraint.split("=")
        cts[k] = v
    return cts


@pytest.fixture
def ams_snap(request):
    return request.config.getoption("--ams-snap")


@pytest.fixture
def charm_path(request):
    return request.config.getoption("--charm")
