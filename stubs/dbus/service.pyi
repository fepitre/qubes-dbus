# Stubs for dbus.service

import dbus
from dbus.connection import Connection
from dbus._dbus import SessionBus
from typing import Any, Optional, Tuple, Union


class Object(dbus.Interface):

    def __init__(self, conn: Optional[Union[BusName,Connection]] = ..., 
				object_path: Optional[str] = ..., 
				bus_name: Optional[BusName] = ...) -> None: ...

    @property
    def _object_path(self) -> str: ...

    def remove_from_connection(self, connection: Connection = None, path: str = None) -> None: ...

def method(
        dbus_interface: str=...,
        in_signature: Optional[str]=...,
        out_signature: Optional[str]=...,
        async_callbacks: Tuple[str,str]=..., 
        sender_keyword: Optional[str]=...,
        path_keyword: Optional[str]=...,
    	rel_path_keyword: Optional[str]=...,
        destination_keyword: Optional[str]=...,
        message_keyword: Optional[str]=...,
        connection_keyword: Optional[str]=...,
        utf8_strings: bool=...,
        byte_arrays: bool=...,

        ) -> Any: ...

def signal(
        dbus_interface: str=...,
        signature: Optional[str]=...,
        path_keyword: Optional[str]=...,
    	rel_path_keyword: Optional[str]=...,
		) -> Any: ...

class BusName(object):
	def __new__(cls,
				name: str,
				bus: Union[dbus.Bus, SessionBus],
				allow_replacement: Optional[bool]=...,
				replace_existing: Optional[bool]=...,
				do_not_queue: Optional[bool]=...,
				) -> BusName: ...
# vim: syntax=python tw=0
