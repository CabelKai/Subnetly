from netaddr import IPNetwork


FULL_LIST_MAX = 32  # /27 IPv4, /123 IPv6


def build_ip_rows(assignment):
    """Returns list of dicts describing IP rows for the subnet edit page.

    Each row dict has:
        address (str), ip_assignment (IPAssignment | None),
        is_full_mode (bool).

    The form per row is built by the view (needs `IPAssignmentForm` import,
    which would cycle through forms.py if done here).
    """
    net = IPNetwork(str(assignment.cidr))
    size = net.size
    existing = {
        str(ip.address): ip for ip in assignment.ip_assignments.all()
    }
    if size <= FULL_LIST_MAX:
        return [
            {
                "address": str(ip),
                "ip_assignment": existing.get(str(ip)),
                "is_full_mode": True,
            }
            for ip in net
        ]
    return [
        {
            "address": addr,
            "ip_assignment": ip,
            "is_full_mode": False,
        }
        for addr, ip in sorted(existing.items(), key=lambda kv: _ip_sort_key(kv[0]))
    ]


def _ip_sort_key(addr_str):
    """Sort key that works for both v4 and v6 addresses."""
    import ipaddress
    return int(ipaddress.ip_address(addr_str))
