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

import unittest
import sys
sys.path.append('lib')  # noqa
sys.path.append('src')  # noqa

from ops.testing import Harness, _TestingModelBackend
from ops.charm import CharmBase
from ops import framework, model

from interface_ceph_iscsi_admin_access.admin_access import (
    CephISCSIAdminAccessRequires,
    CephISCSIAdminAccessProvides)


class TestCephISCSIAdminAccessRequires(unittest.TestCase):

    class MyCharm(CharmBase):

        def __init__(self, *args):
            super().__init__(*args)
            self.seen_events = []
            self.iscsi_user = CephISCSIAdminAccessRequires(
                self,
                'iscsi-dashboard')
            self.framework.observe(
                self.iscsi_user.on.admin_access_ready,
                self._log_event)

        def _log_event(self, event):
            self.seen_events.append(type(event).__name__)

    def setUp(self):
        super().setUp()
        self.harness = Harness(
            self.MyCharm,
            meta='''
name: my-charm
requires:
  iscsi-dashboard:
    interface: admin-access
'''
        )

    def test_init(self):
        self.harness.begin()
        self.assertEqual(
            self.harness.charm.iscsi_user.relation_name,
            'iscsi-dashboard')

    def add_iscsi_relation(self, iscsi_app_name='ceph-iscsi',
                           complete=True):
        rel_id = self.harness.add_relation(
            'iscsi-dashboard',
            iscsi_app_name)
        self.harness.add_relation_unit(
            rel_id,
            '{}/0'.format(iscsi_app_name))
        if complete:
            self.complete_relation(rel_id, iscsi_app_name)
        return rel_id

    def complete_relation(self, rel_id, iscsi_app_name='ceph-iscsi'):
        unit_name = '{}/0'.format(iscsi_app_name)
        self.harness.update_relation_data(
            rel_id,
            unit_name,
            {
                'name': unit_name.replace('/', '-'),
                'host': '{}1.foo'.format(iscsi_app_name),
                'scheme': 'http',
                'port': '23'})
        self.harness.update_relation_data(
            rel_id,
            iscsi_app_name,
            {
                'username': 'admin',
                'password': 'password'})

    def test_add_iscsi_dashboard_relation(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id = self.add_iscsi_relation(complete=False)
        self.assertEqual(
            self.harness.charm.seen_events,
            [])
        self.complete_relation(rel_id)
        self.assertEqual(
            self.harness.charm.seen_events,
            ['CephISCSIAdminAccessEvent'])

    def test_get_user_creds(self):
        self.harness.begin()
        self.harness.set_leader()
        expect_east = {
            'host': 'ceph-iscsi-east1.foo',
            'name': 'ceph-iscsi-east-0',
            'password': 'password',
            'port': '23',
            'scheme': 'http',
            'username': 'admin'}
        expect_west = {
            'host': 'ceph-iscsi-west1.foo',
            'name': 'ceph-iscsi-west-0',
            'password': 'password',
            'port': '23',
            'scheme': 'http',
            'username': 'admin'}
        self.add_iscsi_relation('ceph-iscsi-east')
        self.assertEqual(
            self.harness.charm.iscsi_user.get_user_creds(),
            [expect_east])
        self.add_iscsi_relation('ceph-iscsi-west')
        self.assertEqual(
            self.harness.charm.iscsi_user.get_user_creds(),
            [expect_east, expect_west])


class TestCephISCSIAdminAccessProvides(unittest.TestCase):

    class MyCharm(CharmBase):

        def __init__(self, *args):
            super().__init__(*args)
            self.seen_events = []

            self.admin_access = CephISCSIAdminAccessProvides(
                self,
                'admin-access')
            self.framework.observe(
                self.admin_access.on.admin_access_request,
                self._log_event)

        def _log_event(self, event):
            self.seen_events.append(type(event).__name__)

    def setUp(self):
        super().setUp()
        self.harness = Harness(
            self.MyCharm,
            meta='''
name: ceph-iscsi
provides:
  admin-access:
    interface: admin-access
'''
        )

        # BEGIN: Workaround until network_get is implemented
        class _TestingOPSModelBackend(_TestingModelBackend):

            def network_get(self, endpoint_name, relation_id=None):
                network_data = {
                    'bind-addresses': [{
                        'interface-name': 'eth0',
                        'addresses': [{
                            'cidr': '10.0.0.0/24',
                            'value': '10.0.0.10'}]}],
                    'ingress-addresses': ['10.0.0.10'],
                    'egress-subnets': ['10.0.0.0/24']}
                return network_data

        self.harness._backend = _TestingOPSModelBackend(
            self.harness._unit_name, self.harness._meta)
        self.harness._model = model.Model(
            self.harness._meta,
            self.harness._backend)
        self.harness._framework = framework.Framework(
            ":memory:",
            self.harness._charm_dir,
            self.harness._meta,
            self.harness._model)
        # END Workaround

    def test_init(self):
        self.harness.begin()
        self.assertEqual(
            self.harness.charm.admin_access.relation_name,
            'admin-access')

    def add_admin_access_relation(self, ingress_address,
                                  app_name='ceph-dashboard'):
        unit_name = '{}/0'.format(app_name)
        rel_id = self.harness.add_relation(
            'admin-access',
            app_name)
        self.harness.add_relation_unit(
            rel_id,
            unit_name)
        self.harness.update_relation_data(
            rel_id,
            unit_name,
            {'ingress-address': ingress_address})
        return rel_id

    def test_get_admin_access_requests(self):
        self.harness.begin()
        self.add_admin_access_relation('10.0.0.12')
        self.add_admin_access_relation('10.0.0.12', 'ceph-client')
        self.assertEqual(
            self.harness.charm.admin_access.get_admin_access_requests(),
            ['admin-access-0', 'admin-access-1'])

    def test_client_addresses(self):
        self.harness.begin()
        self.add_admin_access_relation('10.0.0.12')
        self.add_admin_access_relation('192.168.9.34', 'ceph-client')
        self.assertEqual(
            self.harness.charm.admin_access.client_addresses,
            ['10.0.0.12', '192.168.9.34'])

    def test_publish_gateway(self):
        self.harness.begin()
        self.harness.set_leader()
        rel_id1 = self.add_admin_access_relation('10.0.0.12')
        rel_id2 = self.add_admin_access_relation('192.168.9.34', 'ceph-client')
        self.harness.charm.admin_access.publish_gateway(
            'foo',
            'admin',
            'password',
            'http',
            '5001')
        unit_data_expect = {
            'host': '10.0.0.10',
            'name': 'foo',
            'port': '5001',
            'scheme': 'http'}
        app_data_expect = {
            'password': 'password',
            'username': 'admin'}
        self.assertEqual(
            self.harness.get_relation_data(rel_id1, 'ceph-iscsi/0'),
            unit_data_expect)
        self.assertEqual(
            self.harness.get_relation_data(rel_id1, 'ceph-iscsi'),
            app_data_expect)
        self.assertEqual(
            self.harness.get_relation_data(rel_id2, 'ceph-iscsi/0'),
            unit_data_expect)
        self.assertEqual(
            self.harness.get_relation_data(rel_id2, 'ceph-iscsi'),
            app_data_expect)
