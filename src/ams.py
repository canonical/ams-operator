#
# Copyright 2024 Canonical Ltd.  All rights reserved.
#

import os

from ops.model import BlockedStatus
import netifaces
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import ops
from charms.operator_libs_linux.v2 import snap
from charms.operator_libs_linux.v1 import systemd
from charms.operator_libs_linux.v0 import passwd
from charms.tls_certificates_interface.v2.tls_certificates import generate_ca, generate_certificate, generate_csr, generate_private_key

SNAP_NAME = "ams"
SNAP_COMMON_PATH = Path(f"/var/snap/{SNAP_NAME}/common")
SERVER_CONFIG_FOLDER = SNAP_COMMON_PATH / "server"
CLIENT_CONFIG_FOLDER = SNAP_COMMON_PATH / "client"
REGISTRY_CONFIG_FOLDER = SNAP_COMMON_PATH / "registry"
AMS_REGISTRY_CERT = REGISTRY_CONFIG_FOLDER / "client.crt"

AMS_CONFIG_PATH = SNAP_COMMON_PATH  / "conf/main.yaml"

AMS_CERT_BASE_PATH =  SNAP_COMMON_PATH / "certs"

AMS_SERVER_CERT_PATH = AMS_CERT_BASE_PATH / "server.crt"
AAR_SERVER_KEY_PATH = AMS_CERT_BASE_PATH / "server.key"

CLIENTS_CERT_PATH = AMS_CERT_BASE_PATH / "clients"
PUBLISHERS_CERT_PATH = AMS_CERT_BASE_PATH / "publishers"

SERVICE = 'snap.ams.ams.service'
SERVICE_DROP_IN_FOLDER = Path(f'/etc/systemd/system/{SERVICE}.d')
SERVICE_DROP_IN_PATH = SERVICE_DROP_IN_FOLDER / '10-ams-unix-socket-chown.conf'
GROUP_NAME = 'ams'


class AMS:

    def __init__(self, charm: ops.CharmBase):
        self._sc = snap.SnapCache()
        self._charm = charm

    def restart(self):
        self._sc['ams'].restart()

    def remove(self):
        self._sc['ams']._remove()

    def install(self):
        try:
            res = self._charm.model.resources.fetch("ams-snap")
        except ops.ModelError:
            res = None

        # FIXME: Install the ams snap from a resource until we make the
        # snaps in the snap store unlisted
        if res is not None and res.stat().st_size:
            snap.install_local(res, classic=False, dangerous=True)
        else:
            self._charm.unit.status = BlockedStatus("Waiting for AMS snap resource")
            return

        ams_snap = self._sc["ams"]
        ams_snap.connect(plug="daemon-notify", slot="core:daemon-notify")
        ams_snap.alias("amc", "amc")

        passwd.add_group(GROUP_NAME)
        passwd.add_user_to_group('ubuntu', GROUP_NAME)
        self._create_systemd_drop_in()

    def _create_systemd_drop_in(self):
        tenv = Environment(loader=FileSystemLoader("templates"))
        template = tenv.get_template("10-ams-unix-socket-chown.conf.j2")
        rendered_content = template.render(
            {
                "group": GROUP_NAME,
            }
        )
        SERVICE_DROP_IN_FOLDER.mkdir(exist_ok=True)
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
        _snap = self._get_snap()
        if not _snap:
            raise snap.SnapNotFoundError(SNAP_NAME)
        return _snap["version"]

    @property
    def installed(self) -> bool:
        _snap = self._get_snap()
        if not _snap:
            return False
        return True

    @staticmethod
    def get_ip_for_interface(interface):
        """Return the ip address associated to the given interface."""
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET not in addresses or "addr" not in addresses[netifaces.AF_INET][0]:
            raise Exception("No IP associated to requested device")
        return addresses[netifaces.AF_INET][0]["addr"]

    def configure(self,
          port: ops.Port,
          storage_config: str,
          listen_address: str,
          ingress_address: str,
    ):
        tenv = Environment(loader=FileSystemLoader("templates"))
        template = tenv.get_template("config.yaml.j2")
        rendered_content = template.render(
            {
                "listen_address": f"{listen_address}:{port.port}",
                "storage_config": storage_config,
            }
        )
        AMS_CONFIG_PATH.write_text(rendered_content)
        self._setup_certs(ingress_address, ingress_address, listen_address)

    def _setup_certs(self, hostname: str, public_ip: str, private_ip: str):

        cert_base_path = os.path.dirname(AMS_CERT_BASE_PATH)
        if not os.path.exists(cert_base_path):
            os.makedirs(cert_base_path, mode=0o0700)

        os.makedirs(CLIENTS_CERT_PATH, 0o700, exist_ok=True)
        os.makedirs(PUBLISHERS_CERT_PATH, 0o700, exist_ok=True)

        if os.path.exists(AMS_SERVER_CERT_PATH) and os.path.exists(AAR_SERVER_KEY_PATH):
            return

        cert, key = self._generate_selfsigned_cert(hostname, public_ip, private_ip)

        with open(os.open(AMS_SERVER_CERT_PATH, os.O_CREAT | os.O_WRONLY, 0o600), "w") as f:
            f.write(str(cert, "UTF-8"))

        with open(os.open(AAR_SERVER_KEY_PATH, os.O_CREAT | os.O_WRONLY, 0o600), "w") as f:
            f.write(str(key, "UTF-8"))

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
                sans_ip=[public_ip,private_ip] )
        cert = generate_certificate(csr=csr, ca=ca_cert, ca_key=ca_key)
        return cert, key

