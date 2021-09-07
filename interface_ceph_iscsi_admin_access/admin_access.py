#!/usr/bin/env python3

# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ops.framework import (
    StoredState,
    EventBase,
    ObjectEvents,
    EventSource,
    Object)


class CephISCSIAdminAccessEvent(EventBase):
    pass


class CephISCSIAdminAccessEvents(ObjectEvents):
    admin_access_ready = EventSource(CephISCSIAdminAccessEvent)
    admin_access_request = EventSource(CephISCSIAdminAccessEvent)


class CephISCSIAdminAccessRequires(Object):

    on = CephISCSIAdminAccessEvents()
    _stored = StoredState()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(
            charm.on[self.relation_name].relation_changed,
            self._on_relation_changed)

    def get_user_creds(self):
        creds = []
        for relation in self.framework.model.relations[self.relation_name]:
            app_data = relation.data[relation.app]
            for unit in relation.units:
                unit_data = relation.data[unit]
                cred_data = {
                    'name': unit_data.get('name'),
                    'host': unit_data.get('host'),
                    'username': app_data.get('username'),
                    'password': app_data.get('password'),
                    'scheme': unit_data.get('scheme'),
                    'port': unit_data.get('port')}
                if all(cred_data.values()):
                    creds.append(cred_data)
        creds = sorted(creds, key=lambda k: k['host'])
        return creds

    def _on_relation_changed(self, event):
        """Handle the relation-changed event."""
        if self.get_user_creds():
            self.on.admin_access_ready.emit()


class CephISCSIAdminAccessProvides(Object):

    on = CephISCSIAdminAccessEvents()
    _stored = StoredState()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(
            charm.on[self.relation_name].relation_joined,
            self._on_relation_joined)

    def get_admin_access_requests(self):
        usernames = [
            f"{r.name}-{r.id}"
            for r in self.framework.model.relations[self.relation_name]]
        return usernames

    def _on_relation_joined(self, event):
        """Handle the relation-changed event."""
        if self.get_admin_access_requests():
            self.on.admin_access_request.emit()

    def publish_gateway(self, name, username, password, scheme, port=5000):
        for relation in self.framework.model.relations[self.relation_name]:
            if self.model.unit.is_leader():
                relation.data[self.model.app]['username'] = username
                relation.data[self.model.app]['password'] = password
            binding = self.framework.model.get_binding(relation)
            relation.data[self.model.unit]['name'] = name
            relation.data[self.model.unit]['scheme'] = scheme
            relation.data[self.model.unit]['port'] = str(port)
            relation.data[self.model.unit]['host'] = str(
                binding.network.bind_address)

    @property
    def client_addresses(self):
        addressees = []
        for relation in self.framework.model.relations[self.relation_name]:
            for unit in relation.units:
                addressees.append(relation.data[unit]['ingress-address'])
        return sorted(addressees)
