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
''' Collection of serialization helpers '''

import re
from typing import Any, Dict, List

import dbus

import qubesadmin
from qubesadmin.devices import DeviceCollection, DeviceInfo
import qubesadmin.vm
from qubesadmin.label import Label
from qubesadmin.vm import QubesVM

DOMAIN_STATE_PROPERTIES = [
    'is_halted',
    'is_paused',
    'is_running',
    'is_qrexec_running',
]

DEVICE_TYPES = ['block', 'pci']


def qubes_data(app):
    ''' Serialize `qubes.Qubes` to a dictionary '''
    # type: (Qubes) -> Dict[dbus.String, Any]
    result = {}
    for prop in app.property_list():
        name = str(prop)
        key = dbus.String(name)
        try:
            result[key] = serialize_val(getattr(app, name))
        except AttributeError:
            result[key] = dbus.String('')

    return result


def serialize_state(state):
    state = state.lower()
    if state == 'crashed':
        return 'Failed'
    elif state in ['transient', 'na']:
        return 'Unknown'
    elif state == 'halted':
        return 'Halted'
    elif state == 'transient':
        return 'Starting'
    elif state == 'running':
        return 'Started'
    else:
        return '=>%s<=' % state


def domain_data(vm: QubesVM) -> Dict[dbus.String, Any]:
    ''' Serializes a `qubes.vm.qubesvm.QubesVM` to a dictionary '''
    result = dbus.Dictionary({}, signature='sv')
    for prop in vm.property_list():
        name = str(prop)
        try:
            value = serialize_val(getattr(vm, name))
        except AttributeError:
            value = dbus.String('')
        result[name] = value

    # Additional data
    result['state'] = serialize_state(vm.get_power_state())
    if vm.name == 'dom0':
        result['networked'] = False
    else:
        result['networked'] = serialize_val(vm.is_networked())

    result['devices'] = dict()  # type: Dict[dbus.String,dbus.Array]
    for dev_type in DEVICE_TYPES:
        dev_collection = device_collection_data(
            vm.devices[dev_type])  # type: dbus.Array
        dbus_dev_type = serialize_val(dev_type)  # type: dbus.String
        result['devices'][dbus_dev_type] = dev_collection

    return result


def devices_data(app):
    result = []
    for vm in app.domains:
        types = ['block', 'pci']
        for dev_class in types:
            dev_collection = vm.devices[dev_class]
            result += serialize_val(dev_collection)
    return result


def label_data(lab: Label) -> Dict[dbus.String, Any]:
    ''' Serialize a `qubes.Label` to a dictionary '''
    result = {}
    for name in dir(lab):
        if name.startswith('_') or callable(getattr(lab, name)):
            continue
        try:
            value = getattr(lab, name)
            result[name] = dbus.String(value)
        except AttributeError:
            result[name] = dbus.String('')
    return result


def serialize_val(value):
    ''' Serialize a property value '''
    # pylint: disable=too-many-return-statements
    if value is None:
        return dbus.String('')
    if isinstance(value, dict):
        return dbus.Dictionary(value, signature='sv')
    elif isinstance(value, bool):
        return dbus.Boolean(value)
    elif isinstance(value, int):
        return dbus.Int32(value)
    elif callable(value):
        return serialize_val(value())
    elif isinstance(value, qubesadmin.label.Label):
        return label_path(value)
    elif isinstance(value, qubesadmin.vm.QubesVM):
        return domain_path(value)
    elif isinstance(value, DeviceCollection):
        return dbus.Array(device_collection_data(value), signature='a{sv}')
    elif isinstance(value, DeviceInfo):
        return dbus.Dictionary(device_data(value), signature='sv')
    elif isinstance(value, re._pattern_type):
        return dbus.String(value.pattern)
    else:
        return dbus.String(value)


def device_collection_data(collection: DeviceCollection) -> dbus.Array:
    return [device_data(dev) for dev in collection.available()]


def device_data(dev):
    return {
        serialize_val(prop): serialize_val(getattr(dev, prop))
        for prop in dir(dev) if not prop.startswith('_')
    }


def label_path(label: Label) -> dbus.ObjectPath:
    ''' Return the D-Bus object path for a `qubes.Label` '''
    return dbus.ObjectPath('/org/qubes/Labels1/labels/' + label.name)


def domain_path(vm: QubesVM) -> dbus.ObjectPath:
    ''' Return the D-Bus object path for a `qubes.vm.qubesvm.QubesVM` '''
    return dbus.ObjectPath('/org/qubes/DomainManager1/domains/' + str(vm.qid))
