from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import User, Membership, Project, Audit, Machine, LoginAttempt
from core.inventory import save_machine

ADMIN_PASSWORD='Test-local-only-password-123!'


def endpoint(project):
    return f'/api/projects/{project.id}/delete/'


def test_confirmation_is_required_and_no_secret_is_logged(setup,client):
    _,project,*_=setup
    for payload in [{'version':project.version}, {'version':project.version,'password':'incorrect-secret'}]:
        assert client.post(endpoint(project),payload,format='json').status_code==400
    project.refresh_from_db();assert project.deleted_at is None
    assert Audit.objects.filter(event='project_delete_denied',target=str(project.id)).count()==1
    assert 'incorrect-secret' not in str(list(Audit.objects.values()))


def test_delete_excludes_every_scoped_endpoint_and_retains_history(setup,client):
    admin,project,env,other=setup
    machine,_=save_machine(admin,project,{'server_name':'retained-history','environment':env.id,'cpu':4,'ram':8})
    response=client.post(endpoint(project),{'version':project.version,'password':ADMIN_PASSWORD},format='json')
    assert response.status_code==200
    project.refresh_from_db();assert project.deleted_at and project.deleted_by==admin and project.archived
    assert Machine.objects.filter(pk=machine.id).exists()
    assert Audit.objects.filter(event='project_deleted',target=str(project.id)).exists()
    assert project.id not in [p['id'] for p in client.get('/api/projects/').json()]
    report=client.get('/api/reports/').json();assert report['totals']['machines']==0 and report['project_count']==1
    for path in [f'/api/projects/{project.id}/machines/',f'/api/projects/{project.id}/overview/',f'/api/machines/{machine.id}/',f'/api/machines/{machine.id}/activity/']:
        assert client.get(path).status_code==404
    assert client.post(f'/api/projects/{project.id}/exports/',{'kind':'inventory'},format='json').status_code==404
    assert client.post(endpoint(project),{'version':project.version,'password':ADMIN_PASSWORD},format='json').status_code==404


def test_permission_role_and_membership_are_independent(setup):
    _,project,*_=setup
    actor=User.objects.create_user('project-manager',password='Manager-Test-Password-2026!')
    membership=Membership.objects.create(user=actor,project=project,role='manager')
    client=APIClient();client.force_authenticate(actor)
    payload={'version':project.version,'password':'Manager-Test-Password-2026!'}
    assert client.post(endpoint(project),payload,format='json').status_code==403
    membership.permissions=['project_delete'];membership.role='editor';membership.save()
    assert client.post(endpoint(project),payload,format='json').status_code==403
    membership.role='manager';membership.save()
    assert client.post(endpoint(project),payload,format='json').status_code==200


def test_global_permission_does_not_grant_membership(setup):
    _,project,*_=setup
    actor=User.objects.create_user('unscoped-delete',password='Unscoped-Test-Password-2026!',independent_permissions=['project_delete'])
    client=APIClient();client.force_authenticate(actor)
    assert client.post(endpoint(project),{'version':project.version,'password':'Unscoped-Test-Password-2026!'},format='json').status_code==404


def test_version_conflict_and_revoked_permission_block_deletion(setup,client):
    _,project,*_=setup
    assert client.post(endpoint(project),{'version':project.version+1,'password':ADMIN_PASSWORD},format='json').status_code==409
    actor=User.objects.create_user('revoked-delete',password='Revoked-Test-Password-2026!',independent_permissions=['project_delete'])
    Membership.objects.create(user=actor,project=project,role='manager')
    cached=User.objects.get(pk=actor.pk)
    actor.independent_permissions=[];actor.save()
    client=APIClient();client.force_authenticate(cached)
    assert client.post(endpoint(project),{'version':project.version,'password':'Revoked-Test-Password-2026!'},format='json').status_code==403
    project.refresh_from_db();assert project.deleted_at is None


def test_confirmation_rate_limit_persists_and_expires(setup,client):
    _,project,*_=setup
    for _ in range(5):
        assert client.post(endpoint(project),{'version':project.version,'password':'wrong'},format='json').status_code==400
    assert client.post(endpoint(project),{'version':project.version,'password':ADMIN_PASSWORD},format='json').status_code==429
    attempt=LoginAttempt.objects.get();assert attempt.failures==5
    attempt.expires_at=timezone.now()-timedelta(seconds=1);attempt.save()
    assert client.post(endpoint(project),{'version':project.version,'password':ADMIN_PASSWORD},format='json').status_code==200
