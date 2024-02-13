#!/usr/bin/env python3
#
# Copyright 2024 Canonical Ltd.  All rights reserved.
#

"""Operator Charm for AMS."""
import logging

from ams import AMS, BackendConfig, ETCDConfig, PrometheusConfig, ServiceConfig
from interfaces.etcd import ETCDEndpointConsumer
from ops.charm import CharmBase, ConfigChangedEvent, InstallEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)


def _is_ua_attached():
    return True


class AmsOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self._snap = AMS(self)
        self.etcd = ETCDEndpointConsumer(self, "etcd")
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.etcd.on.available, self._on_etcd_available)

    @property
    def private_ip(self) -> str:
        """Private address of the unit."""
        return self.model.get_binding("juju-info").network.bind_address.exploded

    def _on_install(self, event: InstallEvent):
        if not _is_ua_attached():
            self.unit.status = BlockedStatus("Waiting for UA attachment")
        self._snap.install()
        self.unit.set_workload_version(self._snap.version)

    def _on_etcd_available(self, _):
        cfg = self.etcd.get_config()
        self._snap.setup_etcd(ca=cfg["ca"], cert=cfg["cert"], key=cfg["key"])
        self.on.config_changed.emit()

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
        self._snap.set_location(self.config["location"], self.config["port"])
        self.unit.set_ports(int(self.config["port"]))
        self.unit.status = ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    main(AmsOperatorCharm)
