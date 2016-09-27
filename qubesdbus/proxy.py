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

from __future__ import absolute_import

import logging

import dbus
from qubes import Qubes
from qubes.ext import Extension, handler
from qubes.vm.qubesvm import QubesVM
from systemd.journal import JournalHandler

import qubesdbus.serialize

from .constants import NAME_PREFIX, PATH_PREFIX, VERSION

try:
    # Check for mypy dependencies pylint: disable=ungrouped-imports
    from typing import Any, Optional, Union  # pylint: disable=unused-import
    from qubesdbus.service import _DbusServiceObject  # pylint:disable=unused-import
except ImportError:
    pass

log = logging.getLogger('qubesdbus.proxy')
log.addHandler(
    JournalHandler(level=logging.INFO, SYSLOG_IDENTIFIER='qubesdbus.proxy'))
log.propagate = False

INTERFACE_NAME = "%s.QubesSignals%s" % (NAME_PREFIX, VERSION)
SESSION_BUS = dbus.SessionBus()
MANAGER_NAME = "%s.DomainManager%s" % (NAME_PREFIX, VERSION)
MANAGER_PATH = "%s/DomainManager%s" % (PATH_PREFIX, VERSION)
GARBAGE = [
    'domain-is-fully-usable',  # only important for internal core-admin?
    'domain-add'
]


def is_garbage(event):
    if event in ['domain-load']:
        return True
    elif event.startswith('property-pre-set'):
        return True
    else:
        return False


class QubesDbusProxy(Extension):
    # pylint: disable=too-few-public-methods,no-self-use
    def __init__(self):
        super(QubesDbusProxy, self).__init__()
        self.domains = {}  # type: Dict[int, bool]
        self.new_vm = []

    @handler('*')
    def forward_vm_event(self, vm, event, *args, **kwargs):
        if is_garbage(event):
            log.debug('Drop %s from %s', event, vm)
            return
        elif event.startswith('property-set:') and not self.new_vm:
            proxy = vm_proxy(vm.qid)
            property_set(proxy, args[0],
                         qubesdbus.serialize.serialize_val(args[1]))
            log.info('VM: %s %s %s %s', vm, event, args, kwargs)
        elif event == 'domain-init' and vm.storage is None:
            # looks like a new vm is created
            self.new_vm.append(vm)
            log.info('VM %s creation begins', vm)
        elif event == 'domain-create-on-disk':
            proxy = app_proxy()
            func = proxy.get_dbus_method('AddDomain',
                                         'org.qubes.DomainManager1')
            data = qubesdbus.serialize.serialize_val(vm)
            create = False
            if not func(data, create):
                log.error('Could not add vm via to dbus DomainManager')
            log.info('Added VM %s', data)
            self.new_vm.remove(vm)
        else:
            log.warn('Unknown %s from %s %s %s', event, vm, args, kwargs)

    @handler('*', system=True)
    def forward_app_event(self, vm, event, *args, **kwargs):
        proxy = app_proxy()
        if is_garbage(event):
            log.debug('Drop %s from %s', event, vm)
            return
        elif event.startswith('property-set:'):
            property_set(proxy, args[0],
                         qubesdbus.serialize.serialize_val(args[1]))
            log.info('App: %s %s %s %s', vm, event, args, kwargs)
        elif event == 'domain-delete':
            func = proxy.get_dbus_method('DelDomain',
                                         'org.qubes.DomainManager1')
            vm = args[0]
            vm_dbus_path = '/org/qubes/DomainManager1/domains/%s' % vm.qid

            if not func(vm_dbus_path, False):
                log.error('Could not add vm via to dbus DomainManager')
            log.info("Removed VM %s", vm)
        else:
            log.warn('Unknown %s from %s %s %s', event, vm, args, kwargs)


def property_set(proxy, name, value):
    # type: (dbus.proxies.ProxyObject, str, Any) -> None
    ''' Helper for setting a property on a helper '''
    func = proxy.get_dbus_method('Set', 'org.freedesktop.DBus.Properties')
    func('', name, value)


def serialize(args):
    result = []
    for val in args:
        if isinstance(val, QubesVM):
            result.append(val.qid)
        else:
            str(val)
    return result


def vm_proxy(qid):
    # type: (int) -> dbus.proxies.ProxyObject
    domain_path = '/'.join([MANAGER_PATH, 'domains', str(qid)])
    return SESSION_BUS.get_object(MANAGER_NAME, domain_path)


def app_proxy():
    return SESSION_BUS.get_object(MANAGER_NAME, MANAGER_PATH)


def get_proxy(obj):
    # type: (Union[Qubes, QubesVM]) -> dbus.proxies.ProxyObject
    identifier = str(obj)
    if isinstance(obj, Qubes):
        return SESSION_BUS.get_object(MANAGER_NAME, MANAGER_PATH)
    elif isinstance(obj, QubesVM):
        domain_path = '/'.join([MANAGER_PATH, 'domains', identifier]).replace(
            '-', '_')
        return SESSION_BUS.get_object(MANAGER_NAME, domain_path)
    else:
        log.error("Unknown sender object %s", obj)
        return
