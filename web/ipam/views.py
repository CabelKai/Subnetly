
import ipaddress

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from netaddr import IPNetwork

from .forms import ApplicationForm, AssignmentForm, PoolForm
from .models import Application, Assignment, Pool
from .services.blocks import compute_blocks
from .services.colors import colors_for_set


def _pool_range(pool):
    net = ipaddress.ip_network(str(pool.cidr), strict=False)
    return str(net.network_address), str(net.broadcast_address)


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


def _app_name_list(assignment):
    return sorted((a.name for a in assignment.applications.all()), key=str.casefold)


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
                b["app_list"] = _app_name_list(src)
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
                "app_list": _app_name_list(a),
            })
        context = {"pool": pool, "blocks": None, "v6_rows": rows}

    # Delete-dialog data: Pool is PROTECTed by any Assignment.
    context["delete_title"] = "Pool löschen?"
    context["delete_action"] = reverse("ipam:pool_delete", kwargs={"pool_id": pool.pk})
    context["delete_blockers"] = [
        f"{a.cidr} ({', '.join(sorted(app.name for app in a.applications.all())) or '—'})"
        for a in db_assignments
    ]
    context["delete_cascade_message"] = ""

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
            form.save_m2m()
            messages.success(request, "Subnetz angelegt.")
            return redirect("ipam:pool_detail", pool_id=pool_id)
    else:
        form = AssignmentForm(initial=initial, pool=pool)
    pool_first, pool_last = _pool_range(pool)
    return render(request, "assignment_form.html", {
        "form": form, "pool": pool,
        "pool_first_ip": pool_first, "pool_last_ip": pool_last,
    })


@login_required
def assignment_edit(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    pool = assignment.pool
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment, pool=pool)
        if form.is_valid():
            form.save()
            messages.success(request, "Subnetz gespeichert.")
            return redirect("ipam:pool_detail", pool_id=pool.pk)
    else:
        form = AssignmentForm(instance=assignment, pool=pool)

    from .forms import IPAssignmentForm
    from .services.ip_list import build_ip_rows
    rows = build_ip_rows(assignment)
    for i, row in enumerate(rows):
        if row.get("reserved_kind"):
            row["form"] = None
            continue
        row["form"] = IPAssignmentForm(
            instance=row["ip_assignment"],
            assignment=assignment,
            initial=None if row["ip_assignment"] else {"address": row["address"]},
            prefix=f"r{i}",
        )

    is_sparse_mode = IPNetwork(str(assignment.cidr)).size > 32
    pool_first, pool_last = _pool_range(pool)

    ip_count = assignment.ip_assignments.count()
    delete_cascade_message = (
        f"Wird mit {ip_count} IP-Zuordnung(en) gelöscht."
        if ip_count else "Wird gelöscht."
    )

    return render(request, "assignment_form.html", {
        "form": form,
        "pool": pool,
        "pool_first_ip": pool_first,
        "pool_last_ip": pool_last,
        "assignment": assignment,
        "ip_rows": rows,
        "is_sparse_mode": is_sparse_mode,
        "delete_title": "Subnetz löschen?",
        "delete_action": reverse("ipam:assignment_delete", kwargs={"assignment_id": assignment.pk}),
        "delete_blockers": [],
        "delete_cascade_message": delete_cascade_message,
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

    blocking_ips = application.ip_assignments.select_related("assignment").all()
    delete_blockers = [
        f"{ip.address} (Subnetz {ip.assignment.cidr})"
        for ip in blocking_ips
    ]
    m2m_count = application.assignments.count()
    if delete_blockers:
        delete_cascade_message = ""
    elif m2m_count:
        delete_cascade_message = f"Wird aus {m2m_count} Subnetz(en) entfernt."
    else:
        delete_cascade_message = "Keine Referenzen — wird komplett entfernt."

    return render(request, "application_detail.html", {
        "application": application,
        "assignments": assignments,
        "delete_title": "Anwendung löschen?",
        "delete_action": reverse("ipam:application_delete", kwargs={"application_id": application.pk}),
        "delete_blockers": delete_blockers,
        "delete_cascade_message": delete_cascade_message,
    })


@login_required
def application_new(request):
    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Anwendung angelegt.")
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
            messages.success(request, "Anwendung gespeichert.")
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
            messages.success(request, "Pool angelegt.")
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
            messages.success(request, "Pool gespeichert.")
            return redirect("ipam:pool_detail", pool_id=pool.id)
    else:
        form = PoolForm(instance=pool)
    return render(request, "pool_form.html", {"form": form, "mode": "edit", "obj": pool})


@login_required
def ip_assignment_save(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method != "POST":
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    from .forms import IPAssignmentForm
    from .models import IPAssignment
    from .services.ip_list import build_ip_rows

    # Detect delete action on a row form (CSRF-protected POST path)
    if request.POST.get("action") == "delete":
        ip_id = request.POST.get("ip_id")
        if ip_id:
            IPAssignment.objects.filter(pk=ip_id, assignment_id=assignment_id).delete()
            messages.success(request, "IP-Zuordnung gelöscht.")
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    address = request.POST.get("address", "")
    instance = IPAssignment.objects.filter(
        assignment=assignment, address=address,
    ).first()
    form = IPAssignmentForm(request.POST, instance=instance, assignment=assignment)

    if form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.assignment = assignment
            if obj.is_gateway:
                IPAssignment.objects.filter(
                    assignment=assignment, is_gateway=True,
                ).exclude(pk=obj.pk or 0).update(is_gateway=False)
            obj.save()
        messages.success(request, "IP-Zuordnung gespeichert.")
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    # Error path: render edit page directly with the invalid form inline
    rows = build_ip_rows(assignment)
    replaced = False
    for row in rows:
        if row["address"] == address:
            row["form"] = form
            replaced = True
        else:
            row["form"] = IPAssignmentForm(
                instance=row["ip_assignment"],
                assignment=assignment,
                initial=None if row["ip_assignment"] else {"address": row["address"]},
            )
    if not replaced:
        rows.append({
            "address": address,
            "ip_assignment": None,
            "form": form,
            "is_full_mode": False,
        })

    subnet_form = AssignmentForm(instance=assignment, pool=assignment.pool)
    is_sparse_mode = IPNetwork(str(assignment.cidr)).size > 32
    pool_first, pool_last = _pool_range(assignment.pool)
    ip_count = assignment.ip_assignments.count()
    delete_cascade_message = (
        f"Wird mit {ip_count} IP-Zuordnung(en) gelöscht."
        if ip_count else "Wird gelöscht."
    )
    return render(request, "assignment_form.html", {
        "form": subnet_form,
        "pool": assignment.pool,
        "pool_first_ip": pool_first,
        "pool_last_ip": pool_last,
        "assignment": assignment,
        "ip_rows": rows,
        "is_sparse_mode": is_sparse_mode,
        "delete_title": "Subnetz löschen?",
        "delete_action": reverse("ipam:assignment_delete", kwargs={"assignment_id": assignment.pk}),
        "delete_blockers": [],
        "delete_cascade_message": delete_cascade_message,
    })


@login_required
def ip_assignment_save_bulk(request, assignment_id):
    """Bulk-save all IP rows of a subnet in one POST."""
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method != "POST":
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    from .forms import IPAssignmentForm
    from .models import IPAssignment
    from .services.ip_list import build_ip_rows

    rows = build_ip_rows(assignment)
    forms_by_row = []
    any_error = False
    any_change = False

    for i, row in enumerate(rows):
        if row.get("reserved_kind"):
            forms_by_row.append((row, None))
            continue
        prefix = f"r{i}"
        instance = row["ip_assignment"]
        f = IPAssignmentForm(
            request.POST,
            instance=instance,
            assignment=assignment,
            prefix=prefix,
        )
        # Skip rows the user didn't touch. The application select is the
        # user-intent signal: if it's empty and no IPAssignment exists yet,
        # there's nothing to save for this row. (`address` cannot serve as
        # the signal — in full-mode it's auto-populated via a hidden input
        # for every row.)
        app_val = request.POST.get(f"{prefix}-application") or ""
        if instance is None and not app_val:
            forms_by_row.append((row, None))
            continue
        if f.is_valid():
            forms_by_row.append((row, f))
            any_change = True
        else:
            forms_by_row.append((row, f))
            any_error = True

    # Multi-gateway guard: the partial unique constraint allows at most one
    # gateway per assignment. Detect the conflict here instead of letting the
    # last row silently overwrite the others' is_gateway flag.
    gateway_forms = [
        f for _, f in forms_by_row
        if f is not None and f.is_valid() and f.cleaned_data.get("is_gateway")
    ]
    if len(gateway_forms) > 1:
        for f in gateway_forms:
            f.add_error(
                "is_gateway",
                "Es darf nur ein Gateway pro Subnetz gesetzt sein.",
            )
        any_error = True

    if not any_error:
        with transaction.atomic():
            for row, f in forms_by_row:
                if f is None:
                    continue
                obj = f.save(commit=False)
                obj.assignment = assignment
                if obj.is_gateway:
                    IPAssignment.objects.filter(
                        assignment=assignment, is_gateway=True,
                    ).exclude(pk=obj.pk or 0).update(is_gateway=False)
                obj.save()
        if any_change:
            messages.success(request, "IP-Zuordnungen gespeichert.")
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)

    # Error path: re-render edit page; build unbound forms for skipped rows.
    for i, (row, f) in enumerate(forms_by_row):
        if row.get("reserved_kind"):
            row["form"] = None
        elif f is not None:
            row["form"] = f
        else:
            row["form"] = IPAssignmentForm(
                instance=row["ip_assignment"],
                assignment=assignment,
                initial=None if row["ip_assignment"] else {"address": row["address"]},
                prefix=f"r{i}",
            )

    subnet_form = AssignmentForm(instance=assignment, pool=assignment.pool)
    is_sparse_mode = IPNetwork(str(assignment.cidr)).size > 32
    pool_first, pool_last = _pool_range(assignment.pool)
    ip_count = assignment.ip_assignments.count()
    delete_cascade_message = (
        f"Wird mit {ip_count} IP-Zuordnung(en) gelöscht."
        if ip_count else "Wird gelöscht."
    )
    return render(request, "assignment_form.html", {
        "form": subnet_form,
        "pool": assignment.pool,
        "pool_first_ip": pool_first,
        "pool_last_ip": pool_last,
        "assignment": assignment,
        "ip_rows": rows,
        "is_sparse_mode": is_sparse_mode,
        "delete_title": "Subnetz löschen?",
        "delete_action": reverse("ipam:assignment_delete", kwargs={"assignment_id": assignment.pk}),
        "delete_blockers": [],
        "delete_cascade_message": delete_cascade_message,
    })


@login_required
def ip_assignment_delete(request, assignment_id, ip_id):
    from .models import IPAssignment
    if request.method != "POST":
        return redirect("ipam:assignment_edit", assignment_id=assignment_id)
    obj = get_object_or_404(IPAssignment, pk=ip_id, assignment_id=assignment_id)
    obj.delete()
    messages.success(request, "IP-Zuordnung gelöscht.")
    return redirect("ipam:assignment_edit", assignment_id=assignment_id)


@login_required
@require_POST
def pool_delete(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    if pool.assignments.exists():
        messages.warning(request, "Pool nicht gelöscht — Zuweisungen vorhanden.")
        return redirect("ipam:pool_detail", pool_id=pool.pk)
    pool.delete()
    messages.success(request, "Pool gelöscht.")
    return redirect("ipam:index")


@login_required
@require_POST
def application_delete(request, application_id):
    app = get_object_or_404(Application, pk=application_id)
    if app.ip_assignments.exists():
        messages.warning(request, "Anwendung nicht gelöscht — IP-Zuordnungen vorhanden.")
        return redirect("ipam:application_detail", application_id=app.pk)
    app.delete()
    messages.success(request, "Anwendung gelöscht.")
    return redirect("ipam:application_list")


@login_required
@require_POST
def assignment_delete(request, assignment_id):
    asgn = get_object_or_404(Assignment, pk=assignment_id)
    pool_id = asgn.pool_id
    asgn.delete()  # CASCADEs to IPAssignments; M2M to Application clears itself
    messages.success(request, "Subnetz gelöscht.")
    return redirect("ipam:pool_detail", pool_id=pool_id)
