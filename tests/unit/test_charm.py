from unittest.mock import MagicMock, patch

import pytest
from ops.testing import Harness

from src.charm import AmsOperatorCharm


@pytest.fixture
def harness(request):
    with patch("ams.snap.SnapCache"):
        harness = Harness(AmsOperatorCharm)
        request.addfinalizer(harness.cleanup)
        harness.begin()
        yield harness


def test_on_install_with_ams_resource(request):
    with patch("ams.snap") as mocked_snap, patch("ams.passwd"), patch("ams.systemd"), patch(
        "ams.SERVICE_DROP_IN_PATH"
    ) as mocked_server_path:
        harness = Harness(AmsOperatorCharm)
        mocked_snap.install_local = MagicMock()
        fake_snap = MagicMock()
        fake_snap._snap_client.get_installed_snaps.return_value = [
            {"name": "ams", "version": "x1"}
        ]
        mocked_snap.SnapCache.return_value = fake_snap
        request.addfinalizer(harness.cleanup)
        harness.begin()
        harness.add_resource("ams-snap", "ams.snap")
        harness.charm.on.install.emit()
        mocked_server_path.parent.mkdir.assert_called_once()
        mocked_snap.install_local.assert_called_once()
