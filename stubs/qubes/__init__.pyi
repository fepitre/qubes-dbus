from typing import (List)
import qubesadmin.vm
class Qubes(object):
    domains = ... # type: List[qubesadmin.vm.QubesVM]
    labels = ... # type: Dict[str,qubes.Label]

class Label(object):
    name = ... # type: str
