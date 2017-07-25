#
# The Qubes OS Project, https://www.qubes-os.org/
#
# Copyright (C) 2016 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#
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

# pylint: disable=invalid-name
''' Service classes '''

import asyncio
import logging
from typing import Any

import dbus
import dbus.mainloop.glib
import dbus.service
from dbus.service import BusName
from systemd.journal import JournalHandler

import gbulb
from qubesadmin import Qubes
from qubesadmin.events import EventsDispatcher

gbulb.install()
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class DbusServiceObject(dbus.service.Object):
    ''' A class implementing a useful shortcut for writing own D-Bus Services
    '''

    def __init__(self, bus_name: BusName, obj_path: str) -> None:
        self.app = Qubes()
        self.events_dispatcher = EventsDispatcher(self.app)
        super().__init__(bus_name=bus_name, object_path=obj_path)

    @asyncio.coroutine
    def run(self):
        yield from self.events_dispatcher.listen_for_events()


class ObjectManager(DbusServiceObject):
    ''' Provides a class implementing the `org.freedesktop.DBus.ObjectManager`
        interface.
    '''

    def __init__(self, name: str, obj_path: str) -> None:
        bus = dbus.SessionBus()
        bus_name = BusName(name, bus=bus, allow_replacement=True,
                           replace_existing=True)
        super().__init__(bus_name=bus_name, obj_path=obj_path)
        self.bus_name = bus_name
        self.bus = bus
        self.managed_objects = []  # type: List[PropertiesObject]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        ''' Returns the domain objects paths and their supported interfaces and
            properties.
        '''  # pylint: disable=protected-access
        return {
            o._object_path: o.properties_iface()
            for o in self.managed_objects
        }


class PropertiesObject(DbusServiceObject):
    # pylint: disable=invalid-name
    ''' Implements `org.freedesktop.DBus.Properties` interface. '''

    def __init__(self, bus_name: BusName, obj_path: str, iface: str,
                 data: dict) -> None:
        assert iface, "No interface provided for PropertiesObject"

        super().__init__(bus_name, obj_path)

        self.properties = data
        self.id = obj_path
        self.iface = iface
        self.log = logging.getLogger(obj_path)
        self.log.addHandler(
            JournalHandler(level=logging.DEBUG, SYSLOG_IDENTIFIER=obj_path))

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Get(self, interface, property_name):
        ''' Returns the property value.
        '''  # pylint: disable=unused-argument
        return self.properties[property_name]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties",
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, _):
        ''' Returns all properties and their values '''
        return self.properties

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, interface: str, name: str, value: Any) -> None:
        ''' Set a property value.
        '''  # pylint: disable=unused-argument
        new_value = value
        old_value = self.properties[name]
        if new_value == old_value:
            self.log.info('%s: Property %s not changed (%s)', self.id, name,
                          old_value)
        else:
            self.properties[name] = value
            self.PropertiesChanged("org.freedesktop.DBus.Properties",
                                   {name: value}, [])

    @dbus.service.signal(dbus_interface='org.freedesktop.DBus.Properties',
                         signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed_properties,
                          invalidated=None):
        ''' This signal is emitted when a property changes.
        '''  # pylint: disable=unused-argument
        # type: (str, Dict[dbus.String, Any], List[dbus.String]) -> None
        for name, value in changed_properties.items():
            self.log.debug('%s: Property %s changed %s', self.id, name, value)

    def properties_iface(self):
        ''' A helper for wrapping the interface around properties. Used by
            `ObjectManager.GetManagedObjects`
        '''
        return {self.iface: self.properties}
