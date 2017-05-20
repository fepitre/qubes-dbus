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

from __future__ import absolute_import

import logging

import dbus
import dbus.mainloop.glib
import dbus.service

from systemd.journal import JournalHandler

from .constants import NAME_PREFIX, PATH_PREFIX, VERSION

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

try:
    # Check mypy types. pylint: disable=ungrouped-imports, unused-import
    from typing import Any
    from dbus._dbus import SessionBus
    from dbus.service import BusName
except ImportError:
    pass


class DbusServiceObject(dbus.service.Object):
    ''' A class implementing a useful shortcut for writing own D-Bus Services
    '''

    def __init__(self, bus=None, bus_name=None, bus_path=None):
        # type: (SessionBus, BusName, str) -> None
        if bus is not None:
            self.bus = bus
        else:
            self.bus = dbus.SessionBus()

        if bus_path is not None:
            self.bus_path = bus_path
        else:
            self.bus_path = ''.join([PATH_PREFIX, '/', self.__class__.__name__,
                                     str(VERSION)])

        if bus_name is not None:
            self.bus_name = bus_name
        else:
            _name = ''.join([NAME_PREFIX, '.', self.__class__.__name__,
                             str(VERSION)])
            self.bus_name = dbus.service.BusName(_name, self.bus)
        super(DbusServiceObject, self).__init__(self.bus_name, self.bus_path)


class ObjectManager(DbusServiceObject):
    ''' Provides a class implementing the `org.freedesktop.DBus.ObjectManager`
        interface.
    '''

    # pylint: disable=too-few-public-methods
    def __init__(self, bus=None, bus_name=None, bus_path=None):
        super(ObjectManager, self).__init__(bus=bus, bus_name=bus_name,
                                            bus_path=bus_path)
        self.managed_objects = []  # type: PropertiesObject

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager",
                         out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        ''' Returns the domain objects paths and their supported interfaces and
            properties.
        '''  # pylint: disable=protected-access
        return {o._object_path: o.properties_iface()
                for o in self.managed_objects}


class PropertiesObject(DbusServiceObject):
    # pylint: disable=invalid-name
    ''' Implements `org.freedesktop.DBus.Properties` interface. '''

    def __init__(self, name, iface, data, *args, **kwargs):
        self.properties = data
        self.id = name
        self.iface = iface
        self.log = logging.getLogger(name)
        self.log.addHandler(
            JournalHandler(level=logging.DEBUG, SYSLOG_IDENTIFIER='qubesdbus.'
                           + name))

        super(PropertiesObject, self).__init__(*args, **kwargs)

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Get(self, interface, property_name):
        ''' Returns the property value.
        ''' # pylint: disable=unused-argument
        return self.properties[property_name]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties",
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, _):
        ''' Returns all properties and their values '''
        return self.properties

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, interface, name, value):  # type: (str, dbus.String, Any) -> None
        ''' Set a property value.
        ''' # pylint: disable=unused-argument
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
        ''' # pylint: disable=unused-argument
        # type: (str, Dict[dbus.String, Any], List[dbus.String]) -> None
        for name, value in changed_properties.items():
            self.log.debug('%s: Property %s changed %s', self.id, name, value)

    def properties_iface(self):
        ''' A helper for wrapping the interface around properties. Used by
            `ObjectManager.GetManagedObjects`
        '''
        return {self.iface: self.properties}
