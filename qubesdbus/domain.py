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
''' D-Bus Domain object '''

import dbus.service
import qubesadmin

import qubesdbus.service

try:
    # Check mypy types. pylint: disable=ungrouped-imports, unused-import
    from typing import Any, Union
    import dbus
    from dbus._dbus import SessionBus
    from dbus.service import BusName
except ImportError:
    pass


class Domain(qubesdbus.service.PropertiesObject):
    ''' `Domain` is managed by `DomainManager1` and represents a domain. Its D-Bus
        object path is `/org/qubes/DomainManager1/domains/QID`
    '''

    def __init__(self, bus, bus_name, bus_path, data):
        # type: (SessionBus, BusName , str, Dict[Union[str,dbus.String], Any]) -> None
        self.properties = data
        bus_path = '/'.join([bus_path, 'domains', str(data['qid'])])
        self.name = data['name']
        super(Domain, self).__init__(self.name, 'org.qubes.Domain1', data,
                                     bus=bus, bus_name=bus_name,
                                     bus_path=bus_path)

    @dbus.service.signal(dbus_interface="org.qubes.Domain")
    def Started(self):
        """ Signal emited when the domain is started """
        pass

    @dbus.service.signal(dbus_interface="org.qubes.Domain")
    def Halted(self):
        """ Signal emited when the domain is halted """
        pass

    @dbus.service.signal(dbus_interface='org.freedesktop.DBus.Properties',
                         signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed_properties,
                          invalidated=None):
        ''' This signal is emitted when a property changes.
        '''  # pylint: disable=unused-argument
        # type: (str, Dict[dbus.String, Any], List[dbus.String]) -> None
        if 'state' in changed_properties:
            value = changed_properties['state']
            if value == 'Running':
                self.Started()
            elif value == 'Halted':
                self.Halted()
        super().PropertiesChanged(interface, changed_properties, invalidated)

    @dbus.service.signal(
        dbus_interface="org.qubes.DomainManager1.domains.Signals",
        signature='s')
    def StartingSignal(self, name):
        self.properties['state'] = name

    @dbus.service.method("org.qubes.Domain", out_signature="b")
    def Shutdown(self):
        app = qubesadmin.Qubes()
        name = str(self.name)
        vm = app.domains[name]
        vm.shutdown(wait=True)
        self.properties['state'] = 'halted'
        return True

    @dbus.service.method("org.qubes.Domain", out_signature="b")
    def Start(self):
        app = qubesadmin.Qubes()
        name = str(self.name)
        vm = app.domains[name]
        vm.start()
        return True
