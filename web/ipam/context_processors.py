from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List

from .models import Assignment, Pool


@dataclass
class _CustomerNode:
    name: str
    id: int = 0
    assignments: List[Assignment] = field(default_factory=list)


@dataclass
class _PoolNode:
    cidr: str
    name: str
    id: int
    ip_version: int
    customers: List[_CustomerNode] = field(default_factory=list)


def sidebar_tree(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"sidebar_pools": []}

    pools = list(Pool.objects.all())
    assignments = (
        Assignment.objects
        .select_related("pool", "customer")
        .order_by("pool__cidr", "customer__name", "cidr")
    )

    by_pool = OrderedDict()
    for p in pools:
        by_pool[p.id] = _PoolNode(
            cidr=str(p.cidr), name=p.name, id=p.id, ip_version=p.ip_version
        )

    for a in assignments:
        pool_node = by_pool[a.pool_id]
        if not pool_node.customers or pool_node.customers[-1].name != a.customer.name:
            pool_node.customers.append(_CustomerNode(name=a.customer.name, id=a.customer.id))
        pool_node.customers[-1].assignments.append(a)

    return {"sidebar_pools": list(by_pool.values())}
