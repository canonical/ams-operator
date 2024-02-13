"""Module to configure AMS for charms."""
#
# Copyright 2024 Canonical Ltd.  All rights reserved.
#

import logging
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import ops
import yaml
from charms.operator_libs_linux.v0 import passwd
from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v2 import snap
from jinja2 import Environment, FileSystemLoader
from ops.model import BlockedStatus

SNAP_NAME = "ams"
SNAP_COMMON_PATH = Path(f"/var/snap/{SNAP_NAME}/common")

ETCD_BASE_PATH = SNAP_COMMON_PATH / "etcd"
ETCD_CA_PATH = ETCD_BASE_PATH / "client-ca.pem"
ETCD_CERT_PATH = ETCD_BASE_PATH / "client-cert.pem"
ETCD_KEY_PATH = ETCD_BASE_PATH / "client-key.pem"

AMS_CONFIG_PATH = SNAP_COMMON_PATH / "server/settings.yaml"
CLIENT_CONFIG_FOLDER = SNAP_COMMON_PATH / "client"
REGISTRY_CONFIG_FOLDER = SNAP_COMMON_PATH / "registry"

AMS_CERT_BASE_PATH = SNAP_COMMON_PATH / "certs"
AMS_REGISTRY_CERT = REGISTRY_CONFIG_FOLDER / "client.crt"
AMS_SERVER_CERT_PATH = AMS_CERT_BASE_PATH / "server.crt"
AAR_SERVER_KEY_PATH = AMS_CERT_BASE_PATH / "server.key"
CLIENTS_CERT_PATH = AMS_CERT_BASE_PATH / "clients"
PUBLISHERS_CERT_PATH = AMS_CERT_BASE_PATH / "publishers"

SERVICE = "snap.ams.ams.service"
SERVICE_DROP_IN_PATH = Path(f"/etc/systemd/system/{SERVICE}.d/10-ams-unix-socket-chown.conf")
GROUP_NAME = "ams"

logger = logging.getLogger(__name__)


@dataclass
class ETCDConfig:
    """Etcd configuration for AMS."""

    use_embedded: bool
    ca: Path = ETCD_CA_PATH
    cert: Path = ETCD_CERT_PATH
    key: Path = ETCD_KEY_PATH
    servers: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """Check if etcd is ready or not."""
        return self.use_embedded or (
            self.ca.exists() and self.cert.exists() and self.key.exists() and bool(self.servers)
        )


@dataclass
class PrometheusConfig:
    """Metrics configuration for AMS."""

    ip: str
    port: int
    tls_cert_path: str
    tls_key_path: str
    basic_auth_username: str
    basic_auth_password: str
    metrics_path: str
    extra_labels: Optional[dict[str, str]] = field(default_factory=dict)
    enabled: bool = False

    def __post_init__(self):
        """Post initialization validations."""
        if self.port > 0:
            self.enabled = True


@dataclass
class BackendConfig:
    """Backend configuration for AMS."""

    port_range: str
    force_tls12: str
    use_network_acl: str
    lxd_project: str
    metrics_server: Optional[str] = ""


@dataclass
class ServiceConfig:
    """Service level configuration for AMS."""

    log_level: str
    ip: str
    port: int
    store: ETCDConfig
    backend: BackendConfig
    metrics: PrometheusConfig


class AMS:
    """Class for handling AMS configurations."""

    def __init__(self, charm: ops.CharmBase):
        self._sc = snap.SnapCache()
        self._charm = charm

    def restart(self):
        """Restart AMS Snap."""
        self._sc["ams"].restart()

    def remove(self):
        """Remove AMS Snap."""
        self._sc["ams"]._remove()

    def install(self):
        """Install AMS including its Snap."""
        try:
            res = self._charm.model.resources.fetch("ams-snap")
        except ops.ModelError:
            res = None

        # FIXME: Install the ams snap from a resource until we make the
        # snaps in the snap store unlisted
        if res is not None and res.stat().st_size:
            snap.install_local(res, classic=False, dangerous=True)
            logger.info("Installed AMS snap from local snap resource")
        else:
            self._charm.unit.status = BlockedStatus("Waiting for AMS snap resource")
            return

        # refresh snap cache after installation
        self._sc._load_installed_snaps()
        ams_snap = self._sc["ams"]
        ams_snap.connect(plug="daemon-notify", slot="core:daemon-notify")
        ams_snap.alias("amc", "amc")

        passwd.add_group(GROUP_NAME)
        passwd.add_user_to_group("ubuntu", GROUP_NAME)
        self._create_systemd_drop_in()

    def setup_etcd(self, ca: str, key: str, cert: str):
        """Create certificates for Etcd."""
        ETCD_BASE_PATH.mkdir(exist_ok=True, parents=True)
        ETCD_CA_PATH.write_text(ca)
        ETCD_CERT_PATH.write_text(cert)
        ETCD_KEY_PATH.write_text(key)

    def _create_systemd_drop_in(self):
        tenv = Environment(loader=FileSystemLoader("templates"))
        template = tenv.get_template("10-ams-unix-socket-chown.conf.j2")
        rendered_content = template.render(
            {
                "group": GROUP_NAME,
            }
        )
        SERVICE_DROP_IN_PATH.parent.mkdir(parents=True, exist_ok=True)
        SERVICE_DROP_IN_PATH.write_text(rendered_content)
        systemd.daemon_reload()

    # TODO: remove this function to get snap from SnapCache()['ams'] after the
    # snap is made publicly available in the snap store
    def _get_snap(self) -> dict | None:
        snaps = self._sc._snap_client.get_installed_snaps()
        for installed_snap in snaps:
            if installed_snap["name"] == SNAP_NAME:
                return installed_snap
        return None

    @property
    def version(self) -> str:
        """Return AMS version."""
        _snap = self._get_snap()
        if not _snap:
            raise snap.SnapNotFoundError(SNAP_NAME)
        return _snap["version"]

    @property
    def installed(self) -> bool:
        """Check if AMS is installed."""
        _snap = self._get_snap()
        if not _snap:
            return False
        return True

    def configure(
        self,
        config: ServiceConfig,
    ):
        """Configure AMS snap."""
        tenv = Environment(loader=FileSystemLoader("templates"))
        template = tenv.get_template("settings.yaml.j2")
        content = asdict(config)
        logger.info(content)
        rendered_content = template.render(content)
        AMS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        AMS_CONFIG_PATH.write_text(rendered_content)

        self._sc["ams"].start(enable=True)

    def set_location(self, location, port):
        """Set location configuration item for AMS."""
        curr_config = self._get_config()
        logger.info(curr_config)
        url = f"https://{location}:{port}"
        if curr_config["load_balancer.url"] == url:
            return
        self._set_config_item("load_balancer.url", url)

    def _get_config(self) -> dict:
        output = subprocess.run(
            ["/snap/bin/amc", "config", "show"], capture_output=True, check=True
        )
        return yaml.safe_load(output.stdout).get("config", {})

    def _set_config_item(self, name, value):
        subprocess.run(["/snap/bin/amc", "config", "set", name, value], check=True)