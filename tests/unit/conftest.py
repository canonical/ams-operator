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

from unittest.mock import patch, MagicMock, PropertyMock
import pytest


@pytest.fixture
def current_version():
    with open("version", "r") as f:
        return f.read().strip("\n")


@pytest.fixture
def mocked_ams():
    with patch("src.charm.AMS") as mocked_ams:
        mock = MagicMock()
        workload_version = "x1"
        type(mock).version = PropertyMock(return_value=workload_version)
        mocked_ams.return_value = mock
        yield mock
