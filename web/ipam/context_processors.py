from collections import OrderedDict

from .models import Application, Assignment, Pool


def sidebar_tree(request):
    """Two flat lists for the left sidebar:
    - sidebar_pools: flat list of pools.
    - sidebar_apps:  each application with its assignments (expandable). With
                     M2M, one assignment may appear under multiple applications.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"sidebar_pools": [], "sidebar_apps": []}

    pools = [
        {"id": p.id, "name": p.name, "cidr": str(p.cidr), "ip_version": p.ip_version}
        for p in Pool.objects.order_by("cidr")
    ]

    assignments = (
        Assignment.objects
        .select_related("pool")
        .prefetch_related("applications")
        .order_by("cidr")
    )

    by_app = OrderedDict()
    for a in assignments:
        for app in a.applications.all():
            node = by_app.setdefault(app.id, {
                "id": app.id,
                "name": app.name,
                "assignments": [],
            })
            node["assignments"].append({
                "cidr": str(a.cidr),
                "pool_id": a.pool_id,
            })

    apps_with_assignments = set(by_app.keys())
    for app in Application.objects.exclude(id__in=apps_with_assignments).order_by("name"):
        by_app[app.id] = {"id": app.id, "name": app.name, "assignments": []}

    sorted_nodes = sorted(by_app.values(), key=lambda n: n["name"].casefold())
    return {"sidebar_pools": pools, "sidebar_apps": sorted_nodes}
