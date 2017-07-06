# -*- encoding: utf-8 -*-
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

''' Forwards qubes-core-admin events to D-Bus. '''

from __future__ import absolute_import

import asyncio
import logging

import dbus
from qubesadmin import Qubes
from qubesadmin.events import EventsDispatcher
from qubesadmin.vm import QubesVM
from systemd.journal import JournalHandler

import qubesdbus.serialize

from .constants import NAME_PREFIX, PATH_PREFIX, VERSION

try:
    # Check for mypy dependencies pylint: disable=ungrouped-imports
    from typing import Any, Optional, Union  # pylint: disable=unused-import
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


class QubesDbusProxy(object):
    # pylint: disable=too-few-public-methods,no-self-use
    def __init__(self):
        super(QubesDbusProxy, self).__init__()
        self.domains = {}  # type: Dict[int, bool]
        self.new_vm = []  # type: List[QubesVM]
        self.app = Qubes()
        self._events_dispatcher = EventsDispatcher(self.app)
        self._events_dispatcher.add_handler('*', self.forward_vm_event)
        self._events_dispatcher.add_handler('*', self.forward_app_event)

    @asyncio.coroutine
    def run(self):
        yield from self._events_dispatcher.listen_for_events()

    def forward_vm_event(self, _, event, *args, **kwargs):
        if 'vm' not in kwargs or event == 'domain-delete':
            return
        try:
            vm = self.app.domains[kwargs['vm']]
            if is_garbage(event):
                log.debug('Drop %s from %s', event, vm)
                return
            elif event.startswith('property-set:') and not self.new_vm:
                proxy = vm_proxy(vm.qid)
                property_set(proxy, kwargs['name'], qubesdbus.serialize.serialize_val(kwargs['newvalue']))
                log.info('VM: %s %s %s %s', vm, event, args, kwargs)
            elif event == 'domain-init' and vm.storage is None:
                # looks like a new vm is created
                self.new_vm.append(vm)
                log.info('VM %s creation begins', vm)
            elif event == 'domain-create-on-disk':
                proxy = app_proxy()
                func = proxy.get_dbus_method('AddDomain',
                                            'org.qubes.DomainManager1')
                data = qubesdbus.serialize.domain_data(vm)
                create = False
                if not func(data, create):
                    log.error('Could not add vm via to dbus DomainManager')
                log.info('Added VM %s', data)
                self.new_vm.remove(vm)
            elif event in ('domain-spawn'):
                proxy = vm_proxy(vm.qid)
                property_set(proxy, 'state', 'Starting')
            elif event == 'domain-start':
                proxy = vm_proxy(vm.qid)
                property_set(proxy, 'state', 'Started')
            elif event == 'domain-pre-shutdown':
                proxy = vm_proxy(vm.qid)
                property_set(proxy, 'state', 'Halting')
            elif event == 'domain-shutdown':
                proxy = vm_proxy(vm.qid)
                if property_get(proxy, 'state') == 'Starting':
                    property_set(proxy, 'state', 'Failed')
                else:
                    property_set(proxy, 'state', 'Halted')
            else:
                log.warn('Unknown %s from %s %s %s', event, vm, args, kwargs)
        except Exception as e:
            log.error(e)

    def forward_app_event(self, _, event, *args, **kwargs):
        try:
            proxy = app_proxy()
            if is_garbage(event):
                log.debug('Drop event %s', event)
                return
            elif event.startswith('property-set:'):
                property_set(proxy, kwargs['name'],
                             qubesdbus.serialize.serialize_val(kwargs['newvalue']))
                log.info('App: %s %s %s', event, args, kwargs)
            elif event == 'domain-delete':
                func = proxy.get_dbus_method('RemoveDomain',
                                             'org.qubes.DomainManager1')
                vm_name = kwargs['vm']

                if not func(vm_name, False):
                    log.error('Could not remove vm via to dbus DomainManager')
                    log.info("Removed VM %s", vm_name)
            else:
                log.warn('Unknown %s %s %s', event, args, kwargs)
        except Exception as e:
            log.warn('Unknown %s %s %s ', event, args, kwargs)


def property_get(proxy: dbus.proxies.ProxyObject, name: str) -> Any:
    ''' Helper for setting a property on a helper '''
    func = proxy.get_dbus_method(
        'Get', dbus_interface='org.freedesktop.DBus.Properties')
    func('', name)


def property_set(proxy: dbus.proxies.ProxyObject, name: str,
                 value: Any) -> None:
    ''' Helper for setting a property on a helper '''
    func = proxy.get_dbus_method(
        'Set', dbus_interface='org.freedesktop.DBus.Properties')
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


def main():
    proxy = QubesDbusProxy()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(proxy.run())
    loop.stop()
    loop.run_forever()
    loop.close()

if __name__ == '__main__':
    main()
