#!/usr/bin/env python3
"""Operator Charm for AMS."""
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

import ast
import json
import logging

from ams import AMS, BackendConfig, ETCDConfig, PrometheusConfig, ServiceConfig
from charms.tls_certificates_interface.v3.tls_certificates import (
    generate_ca,
    generate_certificate,
    generate_csr,
    generate_private_key,
)
from interfaces.etcd import ETCDEndpointConsumer
from ops.charm import (
    CharmBase,
    ConfigChangedEvent,
    InstallEvent,
    RelationDepartedEvent,
    RelationJoinedEvent,
    StopEvent,
    UpgradeCharmEvent,
)
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)


def _is_pro_attached():
    return True


class AmsOperatorCharm(CharmBase):
    """Charm the service."""

    _state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self._snap = AMS(self)
        self._state.set_default(registered_clients=set())
        self.etcd = ETCDEndpointConsumer(self, "etcd")
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.etcd.on.available, self._on_etcd_available)
        self.framework.observe(
            self.on["lxd-cluster"].relation_joined, self._on_lxd_integrator_joined
        )
        self.framework.observe(self.on["rest-api"].relation_joined, self._on_rest_api_joined)
        self.framework.observe(self.on["rest-api"].relation_departed, self._on_rest_api_departed)

    @property
    def public_ip(self) -> str:
        """Public address of the unit."""
        return self.model.get_binding("juju-info").network.ingress_address.exploded

    @property
    def private_ip(self) -> str:
        """Private address of the unit."""
        return self.model.get_binding("juju-info").network.bind_address.exploded

    def _on_install(self, event: InstallEvent):
        if not _is_pro_attached():
            self.unit.status = BlockedStatus("Waiting for Ubuntu Pro attachment")
        self._snap.install()
        self.unit.set_workload_version(self._snap.version)

    def _on_upgrade(self, _: UpgradeCharmEvent):
        # TODO: remove this when the snaps are available from the snap store
        # upgrading does not make sense right now as the snaps have been
        # installed from a local resource.
        self._snap.install()

    def _on_stop(self, _: StopEvent):
        self._snap.remove()

    def _on_config_changed(self, event: ConfigChangedEvent):
        self.unit.status = WaitingStatus("Configuring AMS")
        etcd_cfg = ETCDConfig(
            use_embedded=self.config["use_embedded_etcd"],
        )
        if not etcd_cfg.is_ready:
            if not self.etcd.is_available:
                self.unit.status = BlockedStatus("Waiting for etcd")
                return
            servers = self.etcd.get_config().get("connection_string", "").split(",")
            logger.info(f"Received servers {servers}")
            if not servers:
                self.unit.status = BlockedStatus("Waiting for etcd")
                return
            etcd_cfg.servers = servers
        backend_cfg = BackendConfig(
            port_range=self.config["port_range"],
            lxd_project=self.config["lxd_project"],
            force_tls12=self.config["force_tls12"],
            use_network_acl=self.config["use_network_acl"],
        )
        if self.config["metrics_server"]:
            backend_cfg.metrics_server = f"influxdb:{self.config['metrics_server']}"

        metrics_cfg = PrometheusConfig(
            ip=self.private_ip,
            port=int(self.config["prometheus_target_port"]),
            tls_cert_path=self.config["prometheus_tls_cert_path"],
            tls_key_path=self.config["prometheus_tls_key_path"],
            basic_auth_username=self.config["prometheus_basic_auth_username"],
            basic_auth_password=self.config["prometheus_basic_auth_password"],
            extra_labels=self.config["prometheus_extra_labels"],
            metrics_path=self.config["prometheus_metrics_path"],
        )
        cfg = ServiceConfig(
            ip=self.private_ip,
            port=int(self.config["port"]),
            log_level=self.config["log_level"],
            metrics=metrics_cfg,
            backend=backend_cfg,
            store=etcd_cfg,
        )
        self._snap.configure(cfg)
        if self.config["location"]:
            self._snap.set_location(self.config["location"], self.config["port"])
        self.unit.set_ports(int(self.config["port"]))
        self.unit.status = ActiveStatus()

    def _on_etcd_available(self, _):
        cfg = self.etcd.get_config()
        self._snap.setup_etcd(ca=cfg["ca"], cert=cfg["cert"], key=cfg["key"])
        self.on.config_changed.emit()

    def _on_lxd_integrator_joined(self, event: RelationJoinedEvent):
        cert, key = AmsOperatorCharm._generate_selfsigned_cert(
            self.public_ip, self.public_ip, self.private_ip
        )
        self._snap.setup_lxd(cert=cert, key=key)
        relation_data = event.relation.data[self.unit]
        relation_data["client_certificates"] = json.dumps([cert.decode("utf-8")])

    def _on_rest_api_joined(self, event: RelationJoinedEvent):
        remote_data = event.relation.data.get(event.unit)
        if not remote_data:
            event.defer()
            return
        client_cert = remote_data.get("client_certificate")
        if not client_cert:
            event.defer()
            logger.error("No client certificate found")
            return
        if not self._snap.is_running:
            event.defer()
            return
        fingerprint = self._snap.register_client(ast.literal_eval(client_cert))
        if fingerprint:
            self._state.registered_clients.add(f"{event.unit.name}:{fingerprint}")
        logger.info("Client registration with AMS complete")
        data = {
            "port": str(self.config["port"]),
            "private_address": self.private_ip,
            "public_address": self.public_ip,
            "node": self.unit.name.replace("/", ""),
        }
        location = self._snap.get_config_item("load_balancer.url")
        if location:
            data["private_address"] = location
        event.relation.data[self.unit].update(data)

    def _on_rest_api_departed(self, event: RelationDepartedEvent):
        fp = None
        for client in self._state.registered_clients:
            client = client.split(":")
            if event.unit.name == client[0]:
                fp = client[1]
                break
        if not fp:
            logger.warning(f"No client found for {event.unit} to unregister")
            return
        self._snap.unregister_client(fp)

    @staticmethod
    def _generate_selfsigned_cert(hostname, public_ip, private_ip) -> tuple[bytes, bytes]:
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


if __name__ == "__main__":  # pragma: nocover
    main(AmsOperatorCharm)
