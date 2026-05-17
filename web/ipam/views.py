
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from netaddr import IPNetwork

from .forms import ApplicationForm, AssignmentForm, PoolForm
from .models import Application, Assignment, Pool
from .services.blocks import compute_blocks
from .services.colors import colors_for_set


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


def _first_app_name(assignment):
    apps = sorted((a.name for a in assignment.applications.all()), key=str.casefold)
    return apps[0] if apps else "—"


def _all_app_names(assignment):
    return ", ".join(sorted((a.name for a in assignment.applications.all()), key=str.casefold)) or "—"


@login_required
def pool_detail(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)

    if pool.ip_version == 4:
        pool_net = IPNetwork(str(pool.cidr))
        db_assignments = list(
            pool.assignments.prefetch_related("applications").all()
        )
        assignments = [
            {"cidr": IPNetwork(str(a.cidr)), "label": _first_app_name(a)}
            for a in db_assignments
        ]
        blocks = compute_blocks(pool_net, assignments)

        color_map = colors_for_set(_first_app_name(a) for a in db_assignments)

        for b in blocks:
            if b["kind"] == "assigned":
                src = next(a for a in db_assignments if IPNetwork(str(a.cidr)) == b["cidr"])
                first_name = _first_app_name(src)
                b["color"] = color_map.get(first_name, "#E5E7EB")
                b["app_names"] = _all_app_names(src)
                b["obj"] = src
            b["width_rem"] = f"{b['size'] * 0.3:.2f}"

        context = {"pool": pool, "blocks": blocks}
    else:
        db_assignments = list(
            pool.assignments.prefetch_related("applications").order_by("cidr")
        )
        rows = []
        for a in db_assignments:
            rows.append({
                "id": a.id,
                "cidr": a.cidr,
                "app_names": _all_app_names(a),
            })
        context = {"pool": pool, "blocks": None, "v6_rows": rows}

    return render(request, "pool_detail.html", context)


@login_required
def assignment_new(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    initial = {}
    if "cidr" in request.GET:
        initial["cidr"] = request.GET["cidr"]
    if request.method == "POST":
        form = AssignmentForm(request.POST, pool=pool)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.pool = pool
            instance.save()
            return redirect("ipam:pool_detail", pool_id=pool_id)
    else:
        form = AssignmentForm(initial=initial, pool=pool)
    return render(request, "assignment_form.html", {"form": form, "pool": pool})


@login_required
def assignment_edit(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    pool = assignment.pool
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment, pool=pool)
        if form.is_valid():
            form.save()
            return redirect("ipam:pool_detail", pool_id=pool.pk)
    else:
        form = AssignmentForm(instance=assignment, pool=pool)

    from .forms import IPAssignmentForm
    from .services.ip_list import build_ip_rows
    rows = build_ip_rows(assignment)
    for row in rows:
        row["form"] = IPAssignmentForm(
            instance=row["ip_assignment"],
            assignment=assignment,
            initial=None if row["ip_assignment"] else {"address": row["address"]},
        )

    return render(request, "assignment_form.html", {
        "form": form,
        "pool": pool,
        "assignment": assignment,
        "ip_rows": rows,
    })


@login_required
def application_list(request):
    applications = Application.objects.annotate(
        n_assignments=Count("assignments")
    ).order_by("name")
    return render(request, "application_list.html", {"applications": applications})


@login_required
def application_detail(request, application_id):
    application = get_object_or_404(Application, pk=application_id)
    assignments = application.assignments.select_related("pool").order_by("pool__cidr", "cidr")
    return render(request, "application_detail.html", {
        "application": application, "assignments": assignments,
    })


@login_required
def application_new(request):
    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("ipam:application_list")
    else:
        form = ApplicationForm()
    return render(request, "application_form.html", {"form": form, "mode": "new"})


@login_required
def application_edit(request, application_id):
    app = get_object_or_404(Application, pk=application_id)
    if request.method == "POST":
        form = ApplicationForm(request.POST, instance=app)
        if form.is_valid():
            form.save()
            return redirect("ipam:application_detail", application_id=app.id)
    else:
        form = ApplicationForm(instance=app)
    return render(request, "application_form.html", {"form": form, "mode": "edit", "obj": app})


@login_required
def pool_new(request):
    if request.method == "POST":
        form = PoolForm(request.POST)
        if form.is_valid():
            pool = form.save()
            return redirect("ipam:pool_detail", pool_id=pool.id)
    else:
        form = PoolForm()
    return render(request, "pool_form.html", {"form": form, "mode": "new"})


@login_required
def pool_edit(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    if request.method == "POST":
        form = PoolForm(request.POST, instance=pool)
        if form.is_valid():
            form.save()
            return redirect("ipam:pool_detail", pool_id=pool.id)
    else:
        form = PoolForm(instance=pool)
    return render(request, "pool_form.html", {"form": form, "mode": "edit", "obj": pool})


@login_required
def ip_assignment_save(request, assignment_id):
    # vollständige Implementierung in Task 13
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)


@login_required
def ip_assignment_delete(request, assignment_id, ip_id):
    # vollständige Implementierung in Task 14
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)
