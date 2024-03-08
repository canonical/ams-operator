#!/usr/bin/env python3

import json
import logging
import tempfile
import requests

import ops
from charms.tls_certificates_interface.v3.tls_certificates import (
    generate_ca,
    generate_certificate,
    generate_csr,
    generate_private_key,
)
from ops.framework import StoredState
from ops.model import WaitingStatus

logger = logging.getLogger(__name__)


class ApplicationCharm(ops.CharmBase):
    """Application charm that connects to database charms."""

    _state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._state.set_default(cert=None, key=None, lxd_nodes=[])
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.client_relation_joined, self._on_client_relation_joined)
        self.framework.observe(self.on.client_relation_changed, self._on_client_relation_changed)

    @property
    def public_ip(self) -> str:
        """Public address of the unit."""
        return self.model.get_binding("juju-info").network.ingress_address.exploded

    @property
    def private_ip(self) -> str:
        """Private address of the unit."""
        return self.model.get_binding("juju-info").network.bind_address.exploded

    def _on_start(self, _):
        self.unit.status = ops.ActiveStatus()

    def _on_client_relation_joined(self, event):
        self._state.cert, self._state.key = self._generate_selfsigned_cert(
            self.public_ip, self.public_ip, self.private_ip
        )
        relation_data = event.relation.data[self.unit]
        relation_data["client_certificate"] = json.dumps(self._state.cert.decode("utf-8"))
        with open('client.key', 'w') as key, open('client.cert', 'w') as cert:
            cert.write(self._state.cert.decode())
            key.write(self._state.key.decode())


    def _on_client_relation_changed(self, event):
        data = event.relation.data[event.unit]
        if not ('public_address' in data or 'port' in data):
            event.defer()
            return
        test_url = f"https://{data['public_address']}:{data['port']}/1.0/instances"
        resp = requests.get(test_url, verify=False, cert=('client.cert', 'client.key'))
        resp.raise_for_status()
        logger.info("Connected to ams successfully with authentication")

        self.unit.status = ops.ActiveStatus()

    def _generate_selfsigned_cert(self, hostname, public_ip, private_ip) -> tuple[bytes, bytes]:
        if not hostname:
            raise Exception("A hostname is required")

        if not public_ip:
            raise Exception("A public IP is required")

        if not private_ip:
            raise Exception("A private IP is required")

        ca_key = generate_private_key(key_size=4096)
        ca_cert = generate_ca(ca_key, hostname)

        key = generate_private_key(key_size=4096)
        csr = generate_csr(
            private_key=key,
            subject=hostname,
            sans_dns=[public_ip, private_ip, hostname],
            sans_ip=[public_ip, private_ip],
        )
        cert = generate_certificate(csr=csr, ca=ca_cert, ca_key=ca_key)
        return cert, key


if __name__ == "__main__":
    ops.main(ApplicationCharm)
