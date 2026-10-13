import io
import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient
from core.models import User, Membership
from core.inventory import save_machine


def machine(admin, project, env, disks=2):
    return save_machine(admin, project, {'server_name':'report-sample','environment':env.id,'application':'Service','cpu':4,'ram':'8','disks':[{'name':f'disk-{i}','size':'10','order':i} for i in range(disks)]})[0]


def test_reports_resources_do_not_multiply_with_disks(setup, client):
    admin, project, env, other = setup
    machine(admin,project,env,4)
    report=client.get('/api/reports/').json()
    assert report['totals']=={'machines':1,'cpu':4,'ram':'8.00','disk':'40.00'}
    assert report['services'][0]['cpu']==4 and report['services'][0]['disk']=='40.00'
    assert report['quality']['missing_ip']==1 and report['project_count']==2
    assert 'credential' not in str(report).lower()


def test_reports_project_isolation_and_filters(setup):
    admin, project, env, other=setup
    machine(admin,project,env)
    machine(admin,other,other.environments.first())
    viewer=User.objects.create_user(username='report-viewer',password='Synthetic-Test-Password!')
    Membership.objects.create(project=project,user=viewer,role='viewer')
    client=APIClient();client.force_authenticate(viewer)
    report=client.get('/api/reports/').json()
    assert report['project_count']==1 and report['totals']['machines']==1
    assert client.get('/api/reports/',{'project':other.id}).status_code==404
    assert client.get('/api/reports/',{'environment':env.id}).status_code==400
    assert client.get('/api/reports/',{'project':project.id,'environment':other.environments.first().id}).status_code==404
    assert client.post(f'/api/projects/{project.id}/exports/',{'kind':'inventory'},format='json').status_code==403


def test_selected_project_export_original_columns(setup, client):
    admin, project, env, other=setup
    machine(admin,project,env,3)
    m=machine(admin,other,other.environments.first());m.server_name='other-machine';m.save()
    response=client.post(f'/api/projects/{project.id}/exports/',{'kind':'inventory','merged':True},format='json')
    assert response.status_code==200
    workbook=load_workbook(io.BytesIO(response.content))
    values=list(workbook.active.values)
    text=str(values)
    assert 'report-sample' in text and 'other-machine' not in text
    assert 'Subnet (CIDR)' in text and 'Application' in text and 'VMs' in text


def test_reports_require_authentication(setup):
    assert APIClient().get('/api/reports/').status_code==403


def test_machine_report_pagination(setup,client):
    from core.models import Machine
    admin,project,env,_=setup
    Machine.objects.bulk_create([Machine(project=project,environment=env,created_by=admin,server_name=f'item-{i:03d}',cpu=1,ram=2) for i in range(51)])
    first=client.get('/api/reports/',{'project':project.id}).json()
    second=client.get('/api/reports/',{'project':project.id,'page':2}).json()
    assert first['totals']['machines']==51 and first['pages']==2
    assert len(first['machines'])==50 and len(second['machines'])==1
    assert first['machines'][0]['server_name']=='item-000'
    assert set(first['machines'][0]) >= {'ip','subnet','gateway','disks','vms','application','id'}
    assert client.get('/api/reports/',{'project':project.id,'page':3}).status_code==400
