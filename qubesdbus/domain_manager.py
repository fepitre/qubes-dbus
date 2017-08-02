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

import asyncio
import logging
import sys
from typing import Any, Dict, List, Union  # pylint: disable=unused-import

import dbus
import dbus.service
from systemd.journal import JournalHandler

import qubesadmin
import qubesdbus.serialize
from qubesdbus.models import Domain
from qubesdbus.service import PropertiesObject
from qubesadmin.events import EventsDispatcher

log = logging.getLogger('qubesdbus.DomainManager1')
log.addHandler(JournalHandler(level=logging.DEBUG, SYSLOG_IDENTIFIER='qubesdbus.domain_manager'))
log.propagate = True

# type aliases
DBusSignalMatch = dbus.connection.SignalMatch
DBusString = Union[str, dbus.String]
DBusProperties = Dict[DBusString, Any]

SERVICE_NAME = 'org.qubes.DomainManager1'
SERVICE_PATH = '/org/qubes/DomainManager1'
INTERFACE = 'org.qubes.DomainManager1'


class DomainManager(PropertiesObject):
    ''' The `DomainManager` is the equivalent to the `qubes.Qubes` object for
        managing domains. Implements:
            * `org.freedesktop.DBus.ObjectManager` interface for acquiring all the
               domains.
            * `org.freedesktop.DBus.Properties` for accessing `qubes.Qubes`
               properties
    '''

    def __init__(self) -> None:
        self.app = qubesadmin.Qubes()
        qubes_data = qubesdbus.serialize.qubes_data(self.app)  # type: DBusProperties
        bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(SERVICE_NAME, bus=bus,
                                        allow_replacement=True,
                                        replace_existing=True)
        super().__init__(bus_name, SERVICE_PATH, INTERFACE, qubes_data)
        self.bus_name = bus_name
        self.bus = bus
        self.signal_matches = {}  # type: Dict[str, List[DBusSignalMatch]]
        self.state_signals = {
            'Starting': self.Starting,
            'Started': self.Started,
            'Failed': self.Failed,
            'Halting': self.Halting,
            'Halted': self.Halted,
            'Unknown': lambda _, __: None,
        }

        self.domains = {
            vm.name: self._proxify_domain(vm)
            for vm in self.app.domains
        }
        self.events_dispatcher.add_handler('domain-add', self._domain_add)
        self.events_dispatcher.add_handler('domain-delete',
                                           self._domain_delete)
        self.events_dispatcher.add_handler('domain-spawn', self._domain_spawn)
        self.events_dispatcher.add_handler('domain-start', self._domain_start)
        self.events_dispatcher.add_handler('domain-pre-shutdown',
                                           self._domain_pre_shutdown)
        self.events_dispatcher.add_handler('domain-shutdown',
                                           self._domain_shutdown)
        self.stats_dispatcher = EventsDispatcher(self.app, api_method='admin.vm.Stats')
        self.stats_dispatcher.add_handler('vm-stats', self._update_stats)

    def _domain_add(self, _, __, **kwargs):
        vm_name = kwargs['vm']
        vm = self.app.domains[vm_name]
        log.info('Added domain %s', vm_name)
        vm_proxy = self._proxify_domain(vm)
        obj_path = vm_proxy._object_path # pylint: disable=protected-access
        self.domains[vm_name] = vm_proxy
        self.DomainAdded(INTERFACE, obj_path)
        return True

    def _domain_delete(self, _, __, **kwargs):
        vm_name = kwargs['vm']
        try:
            vm_proxy = self.domains[vm_name]
            obj_path = vm_proxy._object_path # pylint: disable=protected-access
            for signal_matcher in self.signal_matches[obj_path]:
                self.bus.remove_signal_receiver(signal_matcher)
            vm_proxy.remove_from_connection()
            del self.domains[vm_name]
            self.DomainRemoved(INTERFACE, obj_path)
            return True
        except KeyError:
            return False

    def _domain_spawn(self, vm, _, **__):
        try:
            vm_proxy = self.domains[vm.name]
        except KeyError:  # just to be sure
            vm_proxy = self._proxify_domain(vm)
            self.domains[vm.name] = vm_proxy
        vm_proxy.Set("org.freedesktop.DBus.Properties", 'state', 'Starting')

    def _domain_start(self, vm, _, **__):
        try:
            vm_proxy = self.domains[vm.name]
        except KeyError:  # just to be sure
            vm_proxy = self._proxify_domain(vm)
            self.domains[vm.name] = vm_proxy
        vm_proxy.Set("org.freedesktop.DBus.Properties", 'state', 'Started')

    def _domain_pre_shutdown(self, vm, _, **__):
        try:
            vm_proxy = self.domains[vm.name]
        except KeyError:  # just to be sure
            vm_proxy = self._proxify_domain(vm)
            self.domains[vm.name] = vm_proxy
        vm_proxy.Set("org.freedesktop.DBus.Properties", 'state', 'Halting')

    def _domain_shutdown(self, vm, _, **__):
        try:
            vm_proxy = self.domains[vm.name]
        except KeyError:  # just to be sure
            vm_proxy = self._proxify_domain(vm)
            self.domains[vm.name] = vm_proxy
        vm_proxy.Set("org.freedesktop.DBus.Properties", 'state', 'Halted')

    def _setup_state_signals(self, vm_proxy: Domain):
        obj_path = vm_proxy._object_path  # pylint: disable=protected-access
        def emit_state_signal(
                dbus_interface,
                changed_properties: DBusProperties,
                invalidated: dbus.Array=None  # pylint: disable=unused-argument
        ) -> None:
            ''' Emit state signal when domain state property is changed. '''
            #assert dbus_interface == 'org.freedesktop.DBus.Properties'
            if 'state' in changed_properties:
                state = changed_properties['state']
                assert state in self.state_signals
                signal_func = self.state_signals[state]
                signal_func(INTERFACE, obj_path)

        signal_match = self.bus.add_signal_receiver(
            emit_state_signal, signal_name="PropertiesChanged",
            dbus_interface='org.freedesktop.DBus.Properties',
            path=obj_path)  # type: DBusSignalMatch

        if obj_path not in self.signal_matches:
            self.signal_matches[obj_path] = list()

        self.signal_matches[obj_path] += [signal_match]

    def _update_stats(self, vm, _, **kwargs):
        try:
            vm_proxy = self.domains[vm.name]
        except KeyError:  # just to be sure
            vm_proxy = self._proxify_domain(vm)
            self.domains[vm.name] = vm_proxy

        changed_properties = {}
        for key, value in kwargs.items():
            if key == 'memory_kb':
                key = 'memory_usage'
                value = int(value)
            if vm_proxy.properties[key] != value:
                vm_proxy.properties[key] = value
                changed_properties[key] = value

        vm_proxy.PropertiesChanged(Domain.INTERFACE, changed_properties, [])

    @asyncio.coroutine
    def run_vm_stats(self):
        yield from self.stats_dispatcher.listen_for_events()

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        ''' Returns the domain objects paths and their supported interfaces and
            properties.
        '''  # pylint: disable=protected-access
        return {
            o._object_path: o.properties_iface()
            for o in self.domains.values()
        }

    @dbus.service.signal(INTERFACE, signature="so")
    def Started(self, interface, obj_path):
        # type: (DBusString, dbus.ObjectPath) -> None
        """ Signal emited when the domain is started and running"""

    @dbus.service.signal(INTERFACE, signature="so")
    def Starting(self, interface, obj_path):
        # type: (DBusString, dbus.ObjectPath) -> None
        """ Signal emited when the domain is starting """

    @dbus.service.signal(INTERFACE, signature="so")
    def Failed(self, interface, obj_path):
        # type: (DBusString, dbus.ObjectPath) -> None
        """ Signal emited when during the start up of the domain something went
        wrong and the domain was halted"""

    @dbus.service.signal(INTERFACE, signature="so")
    def Halting(self, interface, obj_path):
        # type: (DBusString, dbus.ObjectPath) -> None
        """ Signal emited when the domain is shutting down"""

    @dbus.service.signal(INTERFACE, signature="so")
    def Halted(self, interface, obj_path):
        # type: (DBusString, dbus.ObjectPath) -> None
        """ Signal emited when the domain is halted"""

    @dbus.service.signal(INTERFACE, signature="so")
    def DomainAdded(self, _, object_path):
        ''' This signal is emitted when a new domain is added '''
        self.log.debug("Emiting DomainAdded signal: %s", object_path)

    @dbus.service.signal(INTERFACE, signature="so")
    def DomainRemoved(self, _, object_path):
        ''' This signal is emitted when a new domain is removed '''
        self.log.debug("Emiting DomainRemoved signal: %s", object_path)

    def _proxify_domain(self, vm):
        # type: (Dict[Union[str,DBusString], Any]) -> Domain
        proxy = Domain(self.bus_name, SERVICE_PATH,
                      qubesdbus.serialize.domain_data(vm))
        self._setup_state_signals(proxy)
        return proxy


def main(args=None):  # pylint: disable=unused-argument
    ''' Main function starting the DomainManager1 service. '''
    loop = asyncio.get_event_loop()
    manager = DomainManager()
    tasks = [
        asyncio.ensure_future(manager.run()),
        asyncio.ensure_future(manager.run_vm_stats())
    ]
    done, _ = loop.run_until_complete(asyncio.wait(tasks,
        return_when=asyncio.FIRST_EXCEPTION))
    for task in done:
        # raise an exception, if any
        task.result()
    loop.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
