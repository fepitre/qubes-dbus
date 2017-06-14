# -*- coding: utf-8 -*-
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

import logging
import sys
from typing import Any, Dict, List, Union

import dbus
import dbus.service
from systemd.journal import JournalHandler

import qubesadmin
import qubesdbus.serialize
from qubesdbus.domain import Domain
from qubesdbus.service import ObjectManager, PropertiesObject

import gi  # isort:skip
gi.require_version('Gtk', '3.0')  # isort:skip
from gi.repository import GLib  # isort:skip pylint:disable=wrong-import-position

log = logging.getLogger('qubesdbus.DomainManager1')
log.addHandler(JournalHandler(level=logging.DEBUG, SYSLOG_IDENTIFIER='qubesdbus.domain_manager'))
log.propagate = True

# type aliases
DBusSignalMatch = dbus.connection.SignalMatch
DBusString = Union[str, dbus.String]
DBusProperties = Dict[DBusString, Any]

INTERFACE = 'org.qubes.DomainManager1'

class DomainManager(PropertiesObject, ObjectManager):
    ''' The `DomainManager` is the equivalent to the `qubes.Qubes` object for
        managing domains. Implements:
            * `org.freedesktop.DBus.ObjectManager` interface for acquiring all the
               domains.
            * `org.freedesktop.DBus.Properties` for accessing `qubes.Qubes`
               properties
    '''

    def __init__(self, qubes_data: DBusProperties, domains: List[DBusProperties]) -> None:
        super(DomainManager, self).__init__('DomainManager1', INTERFACE, qubes_data)
        self.managed_objects = [self._proxify_domain(vm) for vm in domains]
        self.state_signals = {
            'Starting': self.Starting,
            'Running' : self.Started,
            'Failed'  : self.Failed,
            'Halting' : self.Halting,
            'Halted'  : self.Halted,
        }
        self.signal_matches = {} # type: Dict[dbus.ObjectPath, List[DBusSignalMatch]]

        for domain in self.managed_objects:
            obj_path = domain._object_path # pylint: disable=protected-access
            self._setup_signals(obj_path)

    def _setup_signals(self, obj_path: dbus.ObjectPath):
        def emit_state_signal(dbus_interface: DBusString,
                              changed_properties: DBusProperties,
                              invalidated: dbus.Array=None  # pylint: disable=unused-argument
                             ) -> None:
            ''' Emit state signal when domain state property is changed. '''
            assert dbus_interface == 'org.freedesktop.DBus.Properties'
            if 'state' in changed_properties:
                state = changed_properties['state']
                assert state in self.state_signals
                signal_func = self.state_signals[state]
                signal_func(INTERFACE, obj_path)

        signal_match = self.bus.add_signal_receiver(
            emit_state_signal,
            signal_name="PropertiesChanged",
            dbus_interface='org.freedesktop.DBus.Properties') # type: DBusSignalMatch

        if obj_path not in self.signal_matches:
            self.signal_matches[obj_path] = list()

        self.signal_matches[obj_path] += signal_match

    @dbus.service.signal(INTERFACE, signature="so")
    def Started(self, interface: DBusString, object_path: dbus.ObjectPath) -> None:
        """ Signal emited when the domain is started and running"""
        pass

    @dbus.service.signal(INTERFACE, signature="so")
    def Starting(self, interface: DBusString, object_path: dbus.ObjectPath) -> None:
        """ Signal emited when the domain is starting """
        pass

    @dbus.service.signal(INTERFACE, signature="so")
    def Failed(self, interface: DBusString, object_path: dbus.ObjectPath) -> None:
        """ Signal emited when during the start up of the domain something went
        wrong and the domain was halted"""
        pass

    @dbus.service.signal(INTERFACE, signature="so")
    def Halting(self, interface: DBusString, object_path: dbus.ObjectPath) -> None:
        """ Signal emited when the domain is shutting down"""
        pass

    @dbus.service.signal(INTERFACE, signature="so")
    def Halted(self, interface: DBusString, object_path: dbus.ObjectPath) -> None:
        """ Signal emited when the domain is halted"""
        pass

    @dbus.service.method(dbus_interface=INTERFACE, in_signature='a{sv}b')
    def AddDomain(self, vm: DBusProperties, execute: bool = False) -> bool:
        ''' Notify the `DomainManager` when a domain is added. This is
            called by `QubesDbusProxy` when 'domain-create-on-disk' event
            arrives from `core-admin`. UI programs which need to create an
            actual vm should set `execute` to True.
        '''
        if execute:
            log.error('Creating domains via DBus is not implemented yet')
            return False

        vm['qid'] = len(self.managed_objects)
        domain = self._proxify_domain(vm)
        self.managed_objects.append(domain)
        log.info('Added domain %s', vm['name'])
        # pylint: disable=protected-access
        obj_path = domain._object_path  # type: dbus.Object_Path
        self._setup_signals(obj_path)
        self.DomainAdded(INTERFACE, obj_path)
        return True

    @dbus.service.signal(INTERFACE, signature="so")
    def DomainAdded(self, _, object_path):
        ''' This signal is emitted when a new domain is added '''
        self.log.debug("Emiting DomainAdded signal: %s", object_path)

    @dbus.service.signal(INTERFACE, signature="so")
    def DomainRemoved(self, _, object_path):
        ''' This signal is emitted when a new domain is removed '''
        self.log.debug("Emiting DomainRemoved signal: %s", object_path)

    @dbus.service.method(dbus_interface=INTERFACE,
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
            obj_path = vm._object_path  # type: dbus.ObjectPath
            if obj_path == vm_dbus_path:
                for signal_matcher in self.signal_matches[obj_path]:
                    self.bus.remove_signal_receiver(signal_matcher)
                vm.remove_from_connection()
                self.managed_objects.remove(vm)
                self.DomainRemoved(INTERFACE, vm._object_path)
                return True
        return False

    def _proxify_domain(self, vm):
        # type: (Dict[Union[str,DBusString], Any]) -> Domain
        return Domain(self.bus, self.bus_name, self.bus_path, vm)


def main(args=None):  # pylint: disable=unused-argument
    ''' Main function starting the DomainManager1 service. '''
    loop = GLib.MainLoop()
    app = qubesadmin.Qubes()
    qubes_data = qubesdbus.serialize.qubes_data(app)
    domains = [qubesdbus.serialize.domain_data(vm) for vm in app.domains]
    _ = DomainManager(qubes_data, domains)
    print("Service running...")
    loop.run()
    print("Service stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
