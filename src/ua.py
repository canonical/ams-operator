"""Ubuntu Pro helper functions."""
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

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class Pro:
    """Class for interacting with Ubuntu Pro Client."""

    UA_STATUS_PATH = Path("/var/lib/ubuntu-advantage/status.json")
    MAX_RETRIES = 30
    MAX_DELAY = 16

    @classmethod
    def enable_anbox_cloud_if_needed(cls):
        """Enable anbox-cloud from ubuntu pro if not enabled."""
        try:
            if not cls._need_enable():
                return
            args = ["ua", "enable", "--access-only", "anbox-cloud"]
            subprocess.run(args, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            if "already enabled" in e.output.decode():
                return
            logger.exception("Failed to enable anbox-cloud subscription %s", e.output.decode())
            raise

    @classmethod
    def _need_enable(cls) -> bool:
        try:
            # If the help command for the anbox-cloud product returns successfully
            # we have a new enough version of the client we can use for enabling
            # the product itself
            args = ["ua", "help", "anbox-cloud"]
            subprocess.run(args, check=True)
            return True
        except Exception as err:
            logger.exception("Anbox Cloud product not supported by the UA client", err)
            return False

    @classmethod
    def is_attached(cls) -> bool:
        """Check if the machine is attached to an ubuntu pro subscription."""
        if not cls.UA_STATUS_PATH.exists():
            return False
        else:
            with open(cls.UA_STATUS_PATH, "r") as f:
                status = json.load(f)
                return status["attached"]
