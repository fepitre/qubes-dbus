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

import qubesdbus.serialize
from qubesdbus.domain import Domain
from qubesdbus.service import PropertiesObject

try:
    # Check mypy types. pylint: disable=ungrouped-imports, unused-import
    from typing import Any, Union
except ImportError:
    pass

log = logging.getLogger('qubesdbus.DomainManager1')
log.addHandler(
    JournalHandler(level=logging.DEBUG,
                   SYSLOG_IDENTIFIER='qubesdbus.domain_manager'))
log.propagate = True


class DomainManager(PropertiesObject):
    def __init__(self, data, domains):
        # type: (Dict[dbus.String, Any], List[Dict[Union[str,dbus.String], Any]]) -> None
        super(DomainManager, self).__init__('DomainManager1', data)
        self.domains = [self._proxify_domain(vm) for vm in domains]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager")
    def GetManagedObjects(self):
        ''' Returns the domain objects paths and their supported interfaces and
            properties.
        '''
        return {"%s/domains/%s" % (self.bus_path, d.properties['qid']):
                # pylint: disable=protected-access
                "%s.domains.%s" % (self.bus_name._name, d.properties['qid'])
                for d in self.domains}

    @dbus.service.method(dbus_interface='org.qubes.DomainManager1',
                         in_signature='a{sv}b')
    def AddDomain(self, vm, execute=False):
        # type: (Dict[dbus.String, Any], bool) -> bool
        if execute:
            log.error('Creating domains via DBus is not implemented yet')
            return False
        else:
            vm['qid'] = len(self.domains)
            domain = self._proxify_domain(vm)
            self.domains.append(domain)
            log.info('Added domain %s', vm['name'])
            # pylint: disable=protected-access
            self.DomainAdded("org.qubes.DomainManager1", domain._object_path)
            return True

    @dbus.service.signal("org.qubes.DomainManager1", signature="so")
    def DomainAdded(self, _, object_path):
        self.log.debug("Emiting DomainAdded signal: %s", object_path)

    @dbus.service.signal("org.qubes.DomainManager1", signature="so")
    def DomainRemoved(self, _, object_path):
        self.log.debug("Emiting DomainRemoved signal: %s", object_path)

    @dbus.service.method(dbus_interface='org.qubes.DomainManager1',
                         in_signature='ob', out_signature='b')
    def RemoveDomain(self, vm_dbus_path, execute=False):
        # type: (dbus.ObjectPath, bool) -> bool
        if execute:
            log.error('Creating domains via DBus is not implemented yet')
            return False
        for vm in self.domains:
            # pylint: disable=protected-access
            if vm._object_path == vm_dbus_path:
                vm.remove_from_connection()
                self.domains.remove(vm)
                self.DomainRemoved("org.qubes.DomainManager1", vm._object_path)
                return True
        return False

    def _proxify_domain(self, vm):
        # type: (Dict[Union[str,dbus.String], Any]) -> Domain
        return Domain(self.bus, self.bus_name, self.bus_path, vm)


def main(args=None):
    ''' Main function '''  # pylint: disable=unused-argument
    loop = GLib.MainLoop()
    app = qubes.Qubes()
    data = qubesdbus.serialize.qubes_data(app)
    domains = [qubesdbus.serialize.domain_data(vm) for vm in app.domains]
    _ = DomainManager(data, domains)
    print("Service running...")
    loop.run()
    print("Service stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
