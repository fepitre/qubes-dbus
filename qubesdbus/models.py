# -*- encoding: utf-8 -*-
# pylint: disable=invalid-name
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
''' Contains models for D-Bus instances we provide.

Contains the folowing interface implementations:
* *org.qubes.Domain*
* *org.qubes.Label*
'''

import os.path
from typing import Any, Dict, Union

import dbus
import dbus.service
from dbus.exceptions import ValidationException
from dbus.service import BusName

import qubesadmin
import qubesdbus.service

DBusString = Union[str, dbus.String]


class Domain(qubesdbus.service.PropertiesObject):
    ''' `Domain` is managed by `DomainManager1` and represents a domain. Its D-Bus
        object path is `/org/qubes/DomainManager1/domains/QID`
    '''
    INTERFACE = 'org.qubes.Domain'

    def __init__(self, bus_name: BusName, path_prefix: str,
                 data: Dict[Union[str, dbus.String], Any]) -> None:
        new_data = {k: v for k, v in data.items() if k not in ['devices']}
        obj_path = os.path.join(path_prefix, 'domains', str(data['qid']))

        super().__init__(bus_name, obj_path, Domain.INTERFACE, new_data)

        self.name = data['name']

        if 'devices' not in data:
            return

        self.devices = []  # type: List[Device]
        self.properties['devices'] = []  # type: List[dbus.ObjectPath]
        for dev_type, dev_col in data['devices'].items():
            if dev_type in ['block', 'pci']:
                for dev_info in dev_col:
                    if dev_type == 'block':
                        dev = BlockDevice(bus_name, obj_path, dev_info)
                    elif dev_type == 'pci':
                        dev = PciDevice(bus_name, obj_path, dev_info)
                    else:
                        assert False, "This should never happen"

                    self.devices.append(dev)
                    self.properties['devices'].append(dev.obj_path)
            else:
                print("Unknown device type %s" % dev_type)
                continue

    @dbus.service.method(dbus_interface="org.freedesktop.DBus.Properties")
    def Set(self, interface: str, name: str, value: Any) -> None:
        ''' Set a property value. '''
        if name == 'state':
            cur_state = self.properties[name]
            state = value
            if not valid_state_change(cur_state, state):
                msg = "State can't change from %s to %s" % (cur_state, state)
                raise ValidationException(msg)
        super().Set(interface, name, value)

    @dbus.service.method("org.qubes.Domain", out_signature="b")
    def Shutdown(self):
        app = qubesadmin.Qubes()
        name = str(self.name)
        vm = app.domains[name]
        vm.shutdown()
        return True

    @dbus.service.method("org.qubes.Domain", out_signature="b")
    def Kill(self):
        app = qubesadmin.Qubes()
        name = str(self.name)
        vm = app.domains[name]
        vm.kill()
        return True

    @dbus.service.method("org.qubes.Domain", out_signature="b")
    def Start(self):
        app = qubesadmin.Qubes()
        name = str(self.name)
        vm = app.domains[name]
        vm.start()
        return True


def valid_state_change(cur_state: DBusString, state: DBusString) -> bool:
    ''' Validates the state changes of a domain. This state don't map one to
        one to the states provided by qubesadmin. The purpose of this states is
        to be user consumable.
        Valid state changes are:
        * UNKNOWN → [STARTED|HALTING]  — workaround Transient state bug
        * FAILED  → STARTING
        * HALTED  → STARTING
        * STARTING → [FAILED|STARTED|HALTED]
        * STARTED → [FAILED|HALTING]
        * HALTING → [FAILED|HALTED]
    '''  # pylint: disable=too-many-boolean-expressions
    all_states = [
        'Unknown', 'Failed', 'Halted', 'Starting', 'Started', 'Halting'
    ]

    if cur_state == state:  # theoretically DBus should take care of this
        return False
    elif cur_state is None and state in all_states\
      or state == 'Unknown' \
      or (cur_state == 'Unknown' and state in ['Started', 'Halting']) \
      or (cur_state == 'Failed'   and state == 'Starting')\
      or (cur_state == 'Halted'   and state == 'Starting')\
      or (cur_state == 'Starting' and state == 'Started')\
      or (cur_state == 'Starting' and state == 'Halted')\
      or (cur_state == 'Started'  and state == 'Halting')\
      or (cur_state == 'Halting'  and state == 'Halted'):
        return True
    elif state == 'Failed':
        return True

    return False


class Label(qubesdbus.service.PropertiesObject):
    ''' Represents a qubes label. Its D-Bus object path is
	`org/qubes/Labels1/labels/COLORNAME`
    '''

    INTERFACE = 'org.qubes.Label1'

    def __init__(self, bus_name, prefix_path, data):
        name = data['name']
        obj_path = os.path.join(prefix_path, 'labels', name)
        super(Label, self).__init__(bus_name, obj_path, Label.INTERFACE, data)


class Device(qubesdbus.service.PropertiesObject):
    ''' Represents a device provided by some domain. Its D-Bus object path is
	`org/qubes/DomainManager1/domains/{DEV_CLASS}/NAME`
    '''

    INTERFACE = 'org.qubes.Device1'

    def __init__(self, bus_name: dbus.service.BusName, obj_path: str,
                 data: dbus.Dictionary) -> None:
        super().__init__(bus_name, obj_path, Device.INTERFACE, data)


class PciDevice(Device):
    ''' Implements the *org.qubes.Device* interface for a pci device. '''

    def __init__(self, bus_name: dbus.service.BusName, prefix_path: str,
                 data: dbus.Dictionary) -> None:
        assert 'libvirt_name' in data[
            'data'], "PCIDevice provided no libvirt_name field"

        obj_path = os.path.join(prefix_path, 'pci',
                                data['data']['libvirt_name'])

        super().__init__(bus_name, obj_path, data)


class BlockDevice(Device):
    ''' Implements the *org.qubes.Device* interface for a block device. '''

    def __init__(self, bus_name: dbus.service.BusName, prefix_path: str,
                 data: dbus.Dictionary) -> None:
        assert 'ident' in data, "BlockDevice provided no ident field"

        ident = os.path.basename(data['ident'])
        obj_path = os.path.join(prefix_path, 'block', ident)

        super().__init__(bus_name, obj_path, data)
