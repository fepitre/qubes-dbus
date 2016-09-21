#!/usr/bin/env python2
# -*- encoding: utf8 -*-
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

# pylint: disable=missing-docstring,invalid-name

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
        # avoid pylint super-on-old-class error
        dbus.service.Object.__init__(self, self.bus_name, self.bus_path)


class PropertiesObject(DbusServiceObject):
    # pylint: disable=invalid-name

    def __init__(self, name, data, *args, **kwargs):
        self.properties = data
        self.id = name
        self.log = logging.getLogger(name)
        self.log.addHandler(
            JournalHandler(level=logging.DEBUG, SYSLOG_IDENTIFIER='qubesdbus.'
                           + name))

        super(PropertiesObject, self).__init__(*args, **kwargs)

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Get(self, _, property_name):
        return self.properties[property_name]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, _, name, value):  # type: (str, dbus.String, Any) -> None
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
    def PropertiesChanged(self, _, changed_properties, __=None):
        # type: (str, Dict[dbus.String, Any], List[dbus.String]) -> None
        for name, value in changed_properties.items():
            self.log.debug('%s: Property %s changed %s', self.id, name, value)
