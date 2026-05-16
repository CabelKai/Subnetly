from collections import OrderedDict

from .models import Application, Assignment, Pool


def sidebar_tree(request):
    """Provide two flat lists for the left sidebar:
    - sidebar_pools: each pool as a direct link to its detail page (no tree)
    - sidebar_apps:  each application with its assignments (expandable)
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"sidebar_pools": [], "sidebar_apps": []}

    pools = [
        {"id": p.id, "name": p.name, "cidr": str(p.cidr), "ip_version": p.ip_version}
        for p in Pool.objects.order_by("cidr")
    ]

    assignments = (
        Assignment.objects
        .select_related("pool", "application")
        .order_by("application__name", "cidr")
    )

    by_app = OrderedDict()
    for a in assignments:
        node = by_app.setdefault(a.application_id, {
            "id": a.application_id,
            "name": a.application.name,
            "assignments": [],
        })
        node["assignments"].append({
            "cidr": str(a.cidr),
            "pool_id": a.pool_id,
        })

    # Include apps with no assignments at the end so they're discoverable.
    apps_with_assignments = set(by_app.keys())
    for app in Application.objects.exclude(id__in=apps_with_assignments).order_by("name"):
        by_app[app.id] = {"id": app.id, "name": app.name, "assignments": []}

    return {"sidebar_pools": pools, "sidebar_apps": list(by_app.values())}
