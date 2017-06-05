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
''' org.qubes.DomainManager1 Service '''

from __future__ import absolute_import, print_function

import logging
import sys

import dbus.service
import qubesadmin
from gi.repository import GLib
from systemd.journal import JournalHandler

import qubesdbus.serialize
from qubesdbus.domain import Domain
from qubesdbus.service import ObjectManager, PropertiesObject

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


class DomainManager(PropertiesObject, ObjectManager):
    ''' The `DomainManager` is the equivalent to the `qubes.Qubes` object for
        managing domains. Implements:
            * `org.freedesktop.DBus.ObjectManager` interface for acquiring all the
               domains.
            * `org.freedesktop.DBus.Properties` for accessing `qubes.Qubes`
               properties
    '''

    def __init__(self, data, domains):
        # type: (Dict[dbus.String, Any], List[Dict[Union[str,dbus.String], Any]]) -> None
        super(DomainManager, self).__init__('DomainManager1',
                                            'org.qubes.DomainManager1', data)
        self.managed_objects = [self._proxify_domain(vm) for vm in domains]

        for domain in self.managed_objects:
            self._setup_signals(domain)

    def _setup_signals(self, obj):
        obj_path = obj._object_path # pylint: disable=protected-access

        self.bus.add_signal_receiver(
            lambda: self.Started("org.qubes.Domain", obj_path),
            signal_name="Started", path=obj_path,
            dbus_interface="org.qubes.Domain")

        self.bus.add_signal_receiver(
            lambda: self.Halted("org.qubes.Domain", obj_path),
            signal_name="Halted", path=obj_path,
            dbus_interface="org.qubes.Domain")


    @dbus.service.method(dbus_interface='org.qubes.DomainManager1',
                         in_signature='a{sv}b')
    def AddDomain(self, vm, execute=False):
        ''' Notify the `DomainManager` when a domain is added. This is
            called by `QubesDbusProxy` when 'domain-create-on-disk' event
            arrives from `core-admin`. UI programs which need to create an
            actual vm should set `execute` to True.
        ''' # type: (Dict[dbus.String, Any], bool) -> bool
        if execute:
            log.error('Creating domains via DBus is not implemented yet')
            return False
        else:
            vm['qid'] = len(self.managed_objects)
            domain = self._proxify_domain(vm)
            self.managed_objects.append(domain)
            log.info('Added domain %s', vm['name'])
            # pylint: disable=protected-access
            self.DomainAdded("org.qubes.DomainManager1", domain._object_path)
            return True

    @dbus.service.signal("org.qubes.DomainManager1", signature="so")
    def DomainAdded(self, _, object_path):
        ''' This signal is emitted when a new domain is added '''
        self.log.debug("Emiting DomainAdded signal: %s", object_path)

    @dbus.service.signal("org.qubes.DomainManager1", signature="so")
    def Halted(self, _, object_path):
        print("Halted %s" % object_path)
        pass

    @dbus.service.signal("org.qubes.DomainManager1", signature="so")
    def Started(self, _, object_path):
        print("Started %s" % object_path)
        pass

    @dbus.service.signal("org.qubes.DomainManager1", signature="so")
    def DomainRemoved(self, _, object_path):
        ''' This signal is emitted when a new domain is removed '''
        self.log.debug("Emiting DomainRemoved signal: %s", object_path)

    @dbus.service.method(dbus_interface='org.qubes.DomainManager1',
                         in_signature='ob', out_signature='b')
    def RemoveDomain(self, vm_dbus_path, execute=False):
        ''' Notify the `DomainManager` when a domain is removed. This is
            called by `QubesDbusProxy` when 'domain-deleted' event
            arrives from `core-admin`. UI programs which need to remove an
            actual vm should set `execute` to True.
        ''' # type: (dbus.ObjectPath, bool) -> bool
        if execute:
            log.error('Creating domains via DBus is not implemented yet')
            return False
        for vm in self.managed_objects:
            # pylint: disable=protected-access
            if vm._object_path == vm_dbus_path:
                vm.remove_from_connection()
                self.managed_objects.remove(vm)
                self.DomainRemoved("org.qubes.DomainManager1", vm._object_path)
                return True
        return False

    def _proxify_domain(self, vm):
        # type: (Dict[Union[str,dbus.String], Any]) -> Domain
        return Domain(self.bus, self.bus_name, self.bus_path, vm)


def main(args=None):  # pylint: disable=unused-argument
    ''' Main function starting the DomainManager1 service. '''
    loop = GLib.MainLoop()
    app = qubesadmin.Qubes()
    data = qubesdbus.serialize.qubes_data(app)
    domains = [qubesdbus.serialize.domain_data(vm) for vm in app.domains]
    _ = DomainManager(data, domains)
    print("Service running...")
    loop.run()
    print("Service stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
