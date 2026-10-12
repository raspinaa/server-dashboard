import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from core.models import *
from core.inventory import save_machine, snapshot, overview
from core.validation import subnet, capacity, network_fields
from core.security import decrypt


def data(env, **extra):
    return {
        "server_name": "sample-01",
        "environment": env.id,
        "application": "Example",
        "vms": "Worker 1",
        "cpu": 4,
        "ram": "8",
        "ip": "192.0.2.11",
        "subnet": "255.255.255.0",
        "gateway": "192.0.2.1",
        "network": "VLAN 20",
        "disks": [{"name": "system", "size": "30", "order": 0}],
        **extra,
    }


@pytest.mark.parametrize(
    "value,expected",
    [
        ("/24", "/24"),
        ("24", "/24"),
        ("255.255.255.0", "/24"),
        ("", ""),
        ("0", "/0"),
        ("/32", "/32"),
    ],
)
def test_subnet(value, expected):
    assert subnet(value) == expected


@pytest.mark.parametrize(
    "value", ["33", "-1", "255.0.255.0", "hello", "255.255.255.1", "/24.0"]
)
def test_bad_subnet(value):
    with pytest.raises(Exception):
        subnet(value)


@pytest.mark.parametrize("value", ["-1", "nan", "Infinity", "1TB", "1.234"])
def test_bad_capacity(value):
    with pytest.raises(Exception):
        capacity(value)


@pytest.mark.parametrize(
    "role,edit,comment",
    [
        ("viewer", False, False),
        ("operator", False, True),
        ("editor", True, True),
        ("manager", True, True),
    ],
)
def test_roles(setup, role, edit, comment):
    admin, p, e, second = setup
    m, _ = save_machine(admin, p, data(e))
    u = User.objects.create_user(role, password="Sample-test-password-only")
    Membership.objects.create(user=u, project=p, role=role)
    c = APIClient()
    c.force_authenticate(u)
    assert c.get(f"/api/projects/{p.id}/machines/").status_code == 200
    assert c.get(f"/api/projects/{second.id}/machines/").status_code == 404
    assert c.patch(
        f"/api/machines/{m.id}/", {"version": 1, "cpu": 5}, format="json"
    ).status_code == (200 if edit else 403)
    assert c.post(
        f"/api/machines/{m.id}/activity/", {"comment": "انجام شد"}, format="json"
    ).status_code == (200 if comment else 403)
    assert c.get("/api/audit/").status_code == 403


def test_edit_history_and_disks(setup, client):
    a, p, e, _ = setup
    m, _ = save_machine(a, p, data(e))
    ident = str(m.id)
    disk = str(m.disks.first().id)
    r = client.patch(
        f"/api/machines/{ident}/",
        {
            "version": 1,
            "server_name": "renamed",
            "cpu": 6,
            "disks": [
                {"id": disk, "name": "root", "size": "50", "order": 1},
                {"name": "data", "size": "60", "order": 0},
            ],
        },
        format="json",
    )
    assert r.status_code == 200, r.data
    assert r.data["machine"]["id"] == ident and len(r.data["machine"]["disks"]) == 2
    assert Change.objects.filter(
        activity__machine=m, field="server_name", previous="sample-01", value="renamed"
    ).exists()
    assert (
        client.patch(
            f"/api/machines/{ident}/", {"version": 1, "cpu": 999}, format="json"
        ).status_code
        == 409
    )
    m.refresh_from_db()
    assert m.cpu == 6
    r = client.patch(
        f"/api/machines/{ident}/", {"version": 2, "disks": []}, format="json"
    )
    assert r.status_code == 200 and not m.disks.exists()


def test_disks_swap(setup):
    a, p, e, _ = setup
    m, _ = save_machine(
        a,
        p,
        data(
            e,
            disks=[
                {"name": "a", "size": 20, "order": 0},
                {"name": "b", "size": 30, "order": 1},
            ],
        ),
    )
    d = snapshot(m)["disks"]
    d[0]["order"] = 1
    d[1]["order"] = 0
    save_machine(a, p, {"version": 1, "disks": d}, m)
    assert list(m.disks.values_list("name", flat=True)) == ["b", "a"]


def test_project_env_isolation(setup, client):
    a, p, e, q = setup
    env = q.environments.first()
    assert (
        client.post(
            f"/api/projects/{p.id}/machines/", data(env), format="json"
        ).status_code
        == 400
    )


def test_credentials(setup, client):
    a, p, e, _ = setup
    m, _ = save_machine(a, p, data(e))
    u = User.objects.create_user("viewer")
    membership = Membership.objects.create(user=u, project=p, role="viewer")
    c = APIClient()
    c.force_authenticate(u)
    assert (
        c.post(
            f"/api/machines/{m.id}/credential/", {"action": "reveal"}, format="json"
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/machines/{m.id}/credential/",
            {"version": 1, "password": "SYNTHETIC-only-credential"},
            format="json",
        ).status_code
        == 200
    )
    m.refresh_from_db()
    assert m.version == 2
    assert m.credential.ciphertext != "SYNTHETIC-only-credential"
    assert "SYNTHETIC-only" not in str(client.get(f"/api/machines/{m.id}/").data)
    membership.permissions = ["credential_view"]
    membership.save()
    r = c.post(f"/api/machines/{m.id}/credential/", {"action": "copy"}, format="json")
    assert r.status_code == 200
    assert r.data["password"] == "SYNTHETIC-only-credential"
    assert r["Cache-Control"] == "no-store"
    assert "SYNTHETIC-only" not in str(list(Audit.objects.values())) + str(
        list(Change.objects.values())
    )
    assert (
        c.post(
            f"/api/projects/{p.id}/exports/", {"credentials": True}, format="json"
        ).status_code
        == 403
    )
    membership.permissions = []
    membership.save()
    assert (
        c.post(f"/api/machines/{m.id}/credential/", {}, format="json").status_code
        == 403
    )


def test_comments_revisions(setup, client):
    a, p, e, _ = setup
    m, _ = save_machine(a, p, data(e))
    r = client.post(
        f"/api/machines/{m.id}/activity/",
        {"comment": "اول", "event": "completed_work"},
        format="json",
    )
    assert r.status_code == 200
    activity = m.activities.get(event="completed_work")
    r = client.patch(
        f"/api/machines/{m.id}/activity/",
        {"id": activity.id, "version": 1, "comment": "دوم"},
        format="json",
    )
    assert r.status_code == 200
    assert activity.revisions.get().previous == "اول"
    assert (
        client.patch(
            f"/api/machines/{m.id}/activity/",
            {"id": activity.id, "version": 1, "comment": "سوم"},
            format="json",
        ).status_code
        == 409
    )
    u = User.objects.create_user("operator")
    Membership.objects.create(user=u, project=p, role="operator")
    c = APIClient()
    c.force_authenticate(u)
    assert (
        c.patch(
            f"/api/machines/{m.id}/activity/",
            {"id": activity.id, "version": 2, "comment": "بدون مجوز"},
            format="json",
        ).status_code
        == 403
    )
    auditactivity = m.activities.get(event="created")
    assert (
        client.patch(
            f"/api/machines/{m.id}/activity/",
            {"id": auditactivity.id, "version": 1, "comment": "changed"},
            format="json",
        ).status_code
        == 404
    )


def test_overview(setup):
    a, p, e, _ = setup
    save_machine(a, p, data(e))
    save_machine(a, p, data(e, server_name="second", cpu=2, ram=4, disks=[]))
    s = overview(p)
    assert (
        s["project"]["cpu"] == 6
        and Decimal(s["project"]["ram"]) == 12
        and Decimal(s["project"]["disk"]) == 30
    )


def test_last_admin(setup, client):
    a, *_ = setup
    r = client.patch("/api/users/", {"id": a.id, "is_admin": False}, format="json")
    assert r.status_code == 400
    assert (
        client.patch(
            "/api/users/", {"id": a.id, "is_active": False}, format="json"
        ).status_code
        == 400
    )


def test_auth_csrf_session(setup):
    c = APIClient(enforce_csrf_checks=True)
    r = c.get("/api/session/")
    assert r.status_code == 200
    assert (
        c.post(
            "/api/login/",
            {"username": "admin", "password": "Test-local-only-password-123!"},
            format="json",
        ).status_code
        == 403
    )
    token = c.cookies["csrftoken"].value
    r = c.post(
        "/api/login/",
        {"username": "admin", "password": "Test-local-only-password-123!"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert r.status_code == 200
    assert c.get("/api/projects/").status_code == 200
    token = c.cookies["csrftoken"].value
    assert (
        c.post(
            "/api/password/",
            {
                "old_password": "Test-local-only-password-123!",
                "new_password": "Updated-Local-Test-Password-234!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 200
    )
    assert (
        c.post("/api/logout/", {}, format="json", HTTP_X_CSRFTOKEN=token).status_code
        == 200
    )
    assert c.get("/api/projects/").status_code == 403


def test_login_throttle(setup):
    c = APIClient()
    c.get("/api/session/")
    for _ in range(5):
        assert (
            c.post(
                "/api/login/", {"username": "admin", "password": "wrong"}, format="json"
            ).status_code
            == 401
        )
    assert (
        c.post(
            "/api/login/", {"username": "admin", "password": "wrong"}, format="json"
        ).status_code
        == 429
    )


def test_ipv6():
    d = {"ip": "2001:db8::1", "gateway": "2001:db8::2", "subnet": "64"}
    assert network_fields(d) == [] and d["subnet"] == "/64"
    with pytest.raises(Exception):
        network_fields({"ip": "bad", "subnet": "24"})


def test_environment_rename(setup, client):
    a, p, e, _ = setup
    m, _ = save_machine(a, p, data(e))
    assert (
        client.patch(
            f"/api/projects/{p.id}/environments/",
            {"id": e.id, "version": 1, "name": "Staging"},
            format="json",
        ).status_code
        == 200
    )
    m.refresh_from_db()
    assert m.environment.name == "Staging" and m.activities.exists()


def test_mysql_engine_collation(db):
    from django.db import connection

    with connection.cursor() as c:
        c.execute(
            'SELECT ENGINE,TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME="core_machine"'
        )
        engine, collation = c.fetchone()
        assert engine == "InnoDB" and collation.startswith("utf8mb4")
        c.execute("SELECT @@sql_mode")
        assert "STRICT_TRANS_TABLES" in c.fetchone()[0]


def test_create_user_and_membership_api(setup, client):
    a, p, e, _ = setup
    r = client.post(
        "/api/users/",
        {
            "username": "new-local-viewer",
            "password": "Only-Test-New-Password-2026!",
            "is_active": True,
            "permissions": [],
        },
        format="json",
    )
    assert r.status_code == 200, r.data
    user = User.objects.get(username="new-local-viewer")
    assert user.check_password("Only-Test-New-Password-2026!")
    assert (
        client.post(
            f"/api/projects/{p.id}/memberships/",
            {"user": user.id, "role": "viewer", "permissions": []},
            format="json",
        ).status_code
        == 200
    )
    assert Membership.objects.get(user=user, project=p).role == "viewer"
