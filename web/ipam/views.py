from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from netaddr import IPNetwork

from .models import Assignment, Pool
from .services.blocks import compute_blocks
from .services.colors import color_for


def _pool_utilization_percent(pool: Pool) -> int:
    pool_net = IPNetwork(str(pool.cidr))
    total = pool_net.size
    used = sum(IPNetwork(str(a.cidr)).size for a in pool.assignments.all())
    return round(used * 100 / total) if total else 0


@login_required
def index(request):
    pools = list(Pool.objects.prefetch_related("assignments"))
    cards = [
        {
            "pool": p,
            "utilization": _pool_utilization_percent(p),
            "assignment_count": p.assignments.count(),
        }
        for p in pools
    ]
    return render(request, "index.html", {"cards": cards})


@login_required
def pool_detail(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)

    if pool.ip_version == 4:
        pool_net = IPNetwork(str(pool.cidr))
        db_assignments = list(pool.assignments.select_related("customer").all())
        assignments = [
            {"cidr": IPNetwork(str(a.cidr)), "label": a.customer.name}
            for a in db_assignments
        ]
        blocks = compute_blocks(pool_net, assignments, block_prefix=pool.block_prefix)

        # Augment assigned blocks with color / customer / ORM obj
        for b in blocks:
            if b["kind"] == "assigned":
                db_a = next(
                    a for a in db_assignments
                    if IPNetwork(str(a.cidr)) == b["cidr"]
                )
                b["color"] = color_for(db_a.customer.name)
                b["customer"] = db_a.customer
                b["obj"] = db_a

        # Grid geometry: total cells = pool size / cell size
        block_prefix = pool.block_prefix or pool_net.prefixlen
        cell_size = 2 ** (32 - block_prefix)
        total_cells = pool_net.size // cell_size
        # Aim for ~16-32 cells per row; pick the largest power-of-two <= sqrt(total)
        import math
        cells_per_row = max(1, 2 ** math.floor(math.log2(max(1, math.isqrt(total_cells)))))

        context = {
            "pool": pool,
            "blocks": blocks,
            "total_cells": total_cells,
            "cells_per_row": cells_per_row,
        }
    else:
        db_assignments = list(
            pool.assignments.select_related("customer").order_by("cidr")
        )
        context = {
            "pool": pool,
            "blocks": None,
            "v6_rows": db_assignments,
        }

    return render(request, "pool_detail.html", context)


@login_required
def assignment_new(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    return render(request, "assignment_form.html", {"pool": pool})


@login_required
def assignment_edit(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    return render(request, "assignment_form.html", {"assignment": assignment})
