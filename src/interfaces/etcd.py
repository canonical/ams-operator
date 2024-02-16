"""ETCD Interface for AMS charm."""
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

import logging

import ops

logger = logging.getLogger(__name__)


class Available(ops.EventBase):
    """Event emitted when a new client is registered."""


class ETCDEvents(ops.ObjectEvents):
    """Event wrapper for ETCD events."""

    available = ops.EventSource(Available)


class ETCDEndpointConsumer(ops.framework.Object):
    """ETCD consumer interface."""

    on: ops.Object = ETCDEvents()
    _state = ops.StoredState()

    def __init__(self, charm: ops.CharmBase, relation_name: str):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._state.set_default(cert="", key="", ca="", connection_string="")
        events = self._charm.on[relation_name]
        self.framework.observe(events.relation_changed, self._on_etcd_changed)

    @property
    def is_available(self):
        """Check if etcd relation is ready."""
        return (
            self._state.ca
            and self._state.cert
            and self._state.key
            and self._state.connection_string
        )

    def _on_etcd_changed(self, event: ops.RelationChangedEvent):
        data = event.relation.data[event.unit]
        self._state.cert = data.get("client_cert")
        self._state.key = data.get("client_key")
        self._state.ca = data.get("client_ca")
        self._state.connection_string = data.get("connection_string")
        if self.is_available:
            self.on.available.emit()

    def get_config(self) -> dict:
        """Get configuration from etcd relation."""
        return {
            "cert": self._state.cert,
            "ca": self._state.ca,
            "key": self._state.key,
            "connection_string": self._state.connection_string,
        }
