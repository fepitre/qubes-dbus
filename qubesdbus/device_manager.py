# -*- encoding: utf-8 -*-
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
''' org.qubes.DeviceManager1 Service '''
import logging
import pprint
import sys

import qubesadmin
import systemd.journal
from gi.repository import GLib

import qubesdbus.serialize
import qubesdbus.service

log = logging.getLogger('qubesdbus.DomainManager1')
log.addHandler(
    systemd.journal.JournalHandler(
        level=logging.DEBUG, SYSLOG_IDENTIFIER='qubesdbus.domain_manager'))
log.propagate = True

pp = pprint.PrettyPrinter()


class DeviceManager(qubesdbus.service.ObjectManager):
    def __init__(self, data):
        super(DeviceManager, self).__init__()
        self.managed_objects = [Device(self.bus, self.bus_name, self.bus_path,
                                       dev) for dev in data]


class Device(qubesdbus.service.PropertiesObject):
    def __init__(self, bus, bus_name, bus_path, data):
        self.properties = data
        pp.pprint(data)
        self.name = data['description']
        bus_path = '/'.join(
            [bus_path, 'devices',  str(data['ident']).replace(".", "/")])
        super(Device, self).__init__(self.name, 'org.qubes.Device1', data,
                                     bus=bus, bus_name=bus_name,
                                     bus_path=bus_path)


def main(args=None):  # pylint: disable=unused-argument
    ''' Main function starting the DomainManager1 service. '''
    loop = GLib.MainLoop()
    app = qubesadmin.Qubes()
    app.domains['dom0'].devices[
        'pci'].available()  # HACK this populates dom0 devices
    devices = qubesdbus.serialize.devices_data(app)
    _ = DeviceManager(devices)
    return loop.run()


if __name__ == '__main__':
    sys.exit(main())
