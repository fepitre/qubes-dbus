from typing import (List)
import qubes.vm
class Qubes(object):
    domains = ... # type: List[qubes.vm.BaseVM]
    labels = ... # type: Dict[str,qubes.Label]

class Label(object):
    name = ... # type: str
