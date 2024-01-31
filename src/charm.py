#!/usr/bin/env python3
#
# Copyright 2024 Canonical Ltd.  All rights reserved.
#

import logging

import ops
from ops.charm import CharmBase, ConfigChangedEvent, InstallEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ams import AMS

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

def is_ua_attached():
    return True

class AmsOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self._snap = AMS(self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_install(self, event: InstallEvent):
        if not is_ua_attached():
            self.unit.status = BlockedStatus("Waiting for UA attachment")
        self._snap.install()
        self.unit.set_workload_version(self._snap.version)

    def _on_config_changed(self, event: ConfigChangedEvent):
        # if not self._snap.installed:
        #     self.unit.status = WaitingStatus("Installing AMS")
        #     self._snap.install()

        # self.unit.status = WaitingStatus("Configuring AMS")
        # port = ops.Port(protocol="tcp", port=int(self.config["port"]))
        # self._snap.configure(port, self.config["storage_config"], self.private_ip, self.public_ip)
        # self.unit.set_ports(port)

        # self._snap.restart()
        self.unit.status = ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    main(AmsOperatorCharm)
