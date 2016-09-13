# -*- encoding: utf8 -*-
# pylint: disable=invalid-name
#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import logging

import dbus.service
from systemd.journal import JournalHandler

try:
    # Check for mypy dependencies pylint: disable=ungrouped-imports
    from typing import Any  # pylint: disable=unused-import
except ImportError:
    pass

DOMAIN_PROPERTIES = ['attached_volumes',
                     'autostart',
                     'backup_timestamp',
                     # 'block_devices',
                     'conf_file',
                     # 'connected_vms',
                     'default_dispvm',
                     'default_user',
                     # 'devices',
                     'dir_path',
                     'dir_path_prefix',
                     'dns',
                     'features',
                     'firewall_conf',
                     'hvm',
                     'icon_path',
                     'include_in_backups',
                     'installed_by_rpm',
                     'internal',
                     'ip',
                     'is_networked',
                     'is_halted',
                     'is_paused',
                     'is_running',
                     'is_qrexec_running',
                     'is_outdated',
                     'kernel',
                     'kernelopts',
                     'label',
                     'mac',
                     'maxmem',
                     'memory',
                     'name',
                     'netmask',
                     'netvm',
                     'qid',
                     'qrexec_timeout',
                     # 'storage',
                     # 'tags',
                     'template',
                     'updateable',
                     'uuid',
                     'vcpus',
                     # 'volumes',
                     'xid', ]

DOMAIN_STATE_PROPERTIES = ['is_halted',
                           'is_paused',
                           'is_running',
                           'is_qrexec_running', ]


class Domain(dbus.service.Object):
    def __init__(self, domain, bus, bus_name, path_prefix):
        self.bus_path = '/'.join([path_prefix, 'domains', str(domain.qid)])
        self.bus_name = bus_name
        self.bus = bus
        self.properties = {'state': 'halted'}
        self.qid = str(domain.qid)
        logger_name = 'qubesdbus.domain.' + self.qid
        self.log = logging.getLogger(logger_name)
        self.log.addHandler(
            JournalHandler(level=logging.DEBUG, SYSLOG_IDENTIFIER=logger_name))

        for p_name in DOMAIN_PROPERTIES:
            try:
                value = getattr(domain, p_name)
                if callable(value):
                    value = value()
                if isinstance(value, dict):
                    value = dbus.Dictionary(value)
                elif isinstance(value, bool):
                    value = dbus.Boolean(value)
                else:
                    value = dbus.String(value)
                if p_name in DOMAIN_STATE_PROPERTIES:
                    if value:
                        self.properties['state'] = p_name.split('_', 1)[1]
                elif p_name.startswith("is_"):
                    _, new_name = p_name.split("_", 1)
                    self.properties[new_name] = value
                else:
                    self.properties[p_name] = value
            except AttributeError:
                self.properties[p_name] = ''
        dbus.service.Object.__init__(self, self.bus_name, self.bus_path)

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Get(self, _, property_name):
        return self.properties[property_name]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def GetAll(self, _):
        # According to the dbus spec we should be able to return types not only
        # string, but it doesn't work. We need to serialize everything to string
        # ☹
        return dbus.Dictionary({k: dbus.String(v)
                                for k, v in self.properties.items()})

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, _, name, value):  # type: (str, dbus.String, Any) -> None
        new_value = value
        old_value = self.properties[name]
        if new_value == old_value:
            self.log.info('%s: Property %s not changed (%s)', self.qid, name,
                          old_value)
        else:
            self.properties[name] = value
            self.PropertiesChanged("org.freedesktop.DBus.Properties",
                                   {name: value}, [])

    @dbus.service.signal(dbus_interface='org.freedesktop.DBus.Properties',
                         signature="sa{sv}as")
    def PropertiesChanged(self, iface_name, changed_properties,
                          invalidated_properties=None):
        # type: (str, Dict[dbus.String, Any], List[dbus.String]) -> None
        for name, value in changed_properties.items():
            self.log.debug('%s: Property %s changed %s', self.qid, name, value)
        pass

    @dbus.service.signal(
        dbus_interface="org.qubes.DomainManager1.domains.Signals",
        signature='s')
    def StateSignal(self, name):
        self.properties['state'] = name

    @dbus.service.signal(
        dbus_interface="org.qubes.DomainManager1.domains.Signals",
        signature='s')
    def StartingSignal(self, name):
        self.properties['state'] = name
