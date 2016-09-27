# Stubs for dbus.proxies
from typing import Optional, Callable

class ProxyObject(object):
    def get_dbus_method(self, member: str=..., dbus_interface: Optional[str]=...) -> Callable: ...

# vim: ft=python tw=0 syntax=python
