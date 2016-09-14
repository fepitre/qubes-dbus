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

from qubesdbus.service import _DbusServiceObject
try:
    # Check for mypy dependencies pylint: disable=ungrouped-imports
    from typing import Any  # pylint: disable=unused-import
except ImportError:
    pass

log = logging.getLogger('org.qubes.Labels1')
log.addHandler(JournalHandler(SYSLOG_IDENTIFIER='qubesdbus.labels'))
log.setLevel(logging.INFO)


class Labels(_DbusServiceObject):
    def __init__(self, app):
        super(Labels, self).__init__()
        self.labels = dbus.Array()
        for label in app.labels.values():
            proxy = Label(label, self.bus, self.bus_name, self.bus_path)
            self.labels.append(proxy)

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.ObjectManager")
    def GetManagedObjects(self):
        ''' Returns all the labels.
        '''
        return {"%s/labels/%s" % (self.bus_path, l.properties['name']):
                "%s.labels.%s" % (self.bus_name, l.properties['name'])
                for l in self.labels}

class Label(dbus.service.Object):
    def __init__(self, label, bus, bus_name, path_prefix):
        self.bus_path = '/'.join([path_prefix, 'labels', label.name])
        self.bus_name = bus_name
        self.bus = bus
        self.properties = {}  # type: Dict[str,Any]
        self.identifier = label.name
        for p_name in dir(label):
            if p_name.startswith('_') or callable(getattr(label, p_name)):
                continue
            try:
                value = getattr(label, p_name)
                self.properties[p_name] = dbus.String(value)
            except AttributeError:
                self.properties[p_name] = ''
        dbus.service.Object.__init__(self, self.bus_name, self.bus_path)

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Get(self, _, property_name):
        return self.properties[property_name]

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def GetAll(self, _):
        # According to the dbus spec we should be able to return types not only
        # string, but it doesn't work. We need to serialize everything to string ☹
        return dbus.Dictionary({k: dbus.String(v)
                                for k, v in self.properties.items()})

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, _, property_name, value):
        log.info('%s: Property changed %s = %s', self.identifier,
                 property_name, value)
        self.properties[property_name] = value

def main(args=None):
    ''' Main function '''  # pylint: disable=unused-argument
    loop = GLib.MainLoop()
    app = qubes.Qubes()
    _ = Labels(app)
    print("Service running...")
    loop.run()
    print("Service stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
