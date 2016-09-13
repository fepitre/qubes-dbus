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

from __future__ import absolute_import, print_function

import logging
import sys

import dbus.service
import qubes
from gi.repository import GLib
from systemd.journal import JournalHandler

from qubesdbus.interface import _QubesDbusInterface
from qubesdbus.service import _DbusServiceObject
from qubesdbus.domain import Domain

try:
    # Check for mypy dependencies pylint: disable=ungrouped-imports
    from typing import Any  # pylint: disable=unused-import
except ImportError:
    pass

log = logging.getLogger('qubesdbus.DomainManager1')
log.addHandler(
    JournalHandler(level=logging.DEBUG,
                   SYSLOG_IDENTIFIER='qubesdbus.domain_manager'))
log.propagate = True

INTERESTING_PROPERTIES = ['clockvm', 'default_dispvm', 'default_fw_netvm',
                          'default_kernel', 'default_netvm',
                          'default_template', 'updatevm']

class DomainManager(_DbusServiceObject, _QubesDbusInterface):
    def __init__(self, app):
        super(DomainManager, self).__init__()
        self.properties = {}  # type: Dict[str, Any]
        self.identifier = str(app)
        self.domains = self.proxify_domains(app.domains)
        for p_name in INTERESTING_PROPERTIES:
            try:
                self.properties[p_name] = str(getattr(app, p_name))
            except AttributeError:
                self.properties[p_name] = ''

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager")
    def GetManagedObjects(self):
        ''' Returns the domain objects paths and their supported interfaces and
            properties.
        '''
        return {"%s/domains/%s" % (self.bus_path, d.qid):
                # pylint: disable=protected-access
                "%s.domains.%s" % (self.bus_name._name, d.qid)
                for d in self.domains}

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Get(self, _, property_name):
        return self.properties[property_name]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def GetAll(self, _):
        return self.properties

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, _, property_name, value):
        log.info('%s: Property changed %s = %s', self.identifier,
                 property_name, value)
        self.properties[property_name] = value

    def proxify_domains(self, domains):
        result = []
        for vm in domains:
            vm_proxy = Domain(vm, self.bus, self.bus_name, self.bus_path)
            result.append(vm_proxy)
        return result

    @dbus.service.method(dbus_interface="org.qubes.Signals1",
                         in_signature='sava{sv}')
    def ForwardSignal(self, event_name, args=None, kwargs=None):
        log.warn('Unknown signal %s received %s', event_name, self.identifier)


def main(args=None):
    ''' Main function '''  # pylint: disable=unused-argument
    loop = GLib.MainLoop()
    app = qubes.Qubes()
    _ = DomainManager(app)
    print("Service running...")
    loop.run()
    print("Service stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
