import base64
import hashlib
import io
import json
import zipfile
from unittest.mock import patch
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient
from core.models import Machine, Environment, User, Membership, Audit, UpdateUpload, SystemSetting
from core.inventory import save_machine
from core.update_bundle import inspect_bundle


def bundle(version='0.4.0', key=None, corrupt=False, extra=None):
    key = key or Ed25519PrivateKey.generate()
    payload = b'synthetic-offline-payload'
    raw = json.dumps({'version': version, 'artifact': f'infrahub-{version}.tar.gz', 'sha256': hashlib.sha256(payload).hexdigest(), 'offline': True, 'mysql':'8.4', 'architectures':['amd64'], 'platforms':['ubuntu-26.04']}).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json', raw)
        archive.writestr('manifest.sig', base64.b64encode(key.sign(raw)))
        archive.writestr(f'infrahub-{version}.tar.gz', payload if not corrupt else b'tampered')
        if extra: archive.writestr(extra, b'unsafe')
    return stream.getvalue(), base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def test_machine_sorting_pagination_and_environment_grouping(setup, client):
    admin, project, env, _ = setup
    second = Environment.objects.create(project=project, name='Production')
    Machine.objects.bulk_create([Machine(project=project, environment=env if i%2 else second, created_by=admin, server_name=f'node-{i:03d}', cpu=i, ram=i) for i in range(65)])
    first=client.get(f'/api/projects/{project.id}/machines/', {'sort':'cpu','direction':'desc'}).json()
    assert first['count']==65 and len(first['results'])==30 and first['pages']==3
    assert [m['environment_name'] for m in first['results']]==['Develop']*30
    assert [m['cpu'] for m in first['results']]==sorted([m['cpu'] for m in first['results']],reverse=True)
    page=client.get(f'/api/projects/{project.id}/machines/', {'page_size':100,'sort':'environment'}).json()
    assert len(page['results'])==65
    assert client.get(f'/api/projects/{project.id}/machines/', {'sort':'credential'}).status_code==400
    assert client.get(f'/api/projects/{project.id}/machines/', {'page_size':100000}).status_code==400
    summary=client.get('/api/reports/', {'summary':1}).json()
    assert not summary['machines'] and summary['totals']['machines']==65


def test_audit_filters_details_and_secret_exclusion(setup, client):
    admin, project, env, _=setup
    machine,_=save_machine(admin,project,{'server_name':'audit-fixture','environment':env.id,'cpu':2,'ram':4})
    from core.security import encrypt
    from core.models import Credential
    Credential.objects.create(machine=machine,ciphertext=encrypt('DO-NOT-LOG-THIS'))
    save_machine(admin,project,{'version':machine.version,'cpu':8},machine)
    event=Audit.objects.get(event='machine_updated')
    detail=client.get(f'/api/audit/{event.id}/').json()
    assert {'field':'cpu','previous':2,'value':8} in detail['changes']
    assert 'DO-NOT-LOG-THIS' not in json.dumps(detail)
    Audit.objects.bulk_create([Audit(user=admin,event='login') for _ in range(38)])
    data=client.get('/api/audit/',{'category':'auth','page_size':30}).json()
    assert data['count']==38 and len(data['results'])==30 and data['pages']==2
    assert client.get('/api/audit/',{'category':'invalid'}).status_code==400
    assert client.get('/api/audit/',{'from':'bad-date'}).status_code==400


def test_user_name_password_and_admin_boundary(setup,client):
    admin,*_=setup
    user=User.objects.create_user('account-old',password='Old-Test-Password-2026!')
    response=client.patch('/api/users/',{'id':user.id,'username':'account-new','password':'New-Test-Password-2026!','is_active':True,'is_admin':False,'permissions':[]},format='json')
    assert response.status_code==200
    user.refresh_from_db();assert user.username=='account-new' and user.check_password('New-Test-Password-2026!')
    user.independent_permissions=['manage_users'];user.save()
    ordinary=APIClient();ordinary.force_authenticate(user)
    assert ordinary.patch('/api/users/',{'id':admin.id,'username':'admin-hijack'},format='json').status_code==403


@pytest.mark.parametrize('kind',['tampered','untrusted','extra'])
def test_bundle_rejects_unsafe_payload(tmp_path,kind):
    raw,key=bundle(corrupt=kind=='tampered',extra='../escape' if kind=='extra' else None)
    path=tmp_path/'bundle.zip';path.write_bytes(raw)
    if kind=='untrusted': _,key=bundle()
    with pytest.raises(Exception):inspect_bundle(path,key,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_privileged_stage_reverifies_and_refuses_file_links(tmp_path, monkeypatch):
    import tarfile, uuid, os
    import update_helper
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        for name in ['deploy/offline/images.tar','deploy/offline/wheels/synthetic.whl']:
            entry=tarfile.TarInfo(name);entry.size=7;archive.addfile(entry,io.BytesIO(b'fixture'))
    key=Ed25519PrivateKey.generate()
    content=payload.getvalue();digest=hashlib.sha256(content).hexdigest()
    raw=json.dumps({'version':'0.4.0','artifact':'infrahub-0.4.0.tar.gz','sha256':digest,'offline':True,'mysql':'8.4','os':'ubuntu-24.04','architectures':['amd64']}).encode()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json',raw);archive.writestr('manifest.sig',base64.b64encode(key.sign(raw)));archive.writestr('infrahub-0.4.0.tar.gz',content)
    root=tmp_path/'installation';root.mkdir();(root/'state').mkdir();folder=root/'data/uploads/updates';folder.mkdir(parents=True)
    (root/'VERSION').write_text('0.3.0');(root/'release-public.key').write_bytes(base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)))
    monkeypatch.setattr(update_helper,'ROOT',root);monkeypatch.setattr('infrahub_cli.os.chown',lambda *args:None)
    identifier=uuid.uuid4();path=folder/f'{identifier.hex}.zip';path.write_bytes(stream.getvalue())
    job={'id':str(identifier),'version':'0.4.0','sha256':digest}
    update_helper.stage_upload(job)
    assert not path.exists() and (root/'state/releases/0.4.0/manifest.json').exists()
    external=tmp_path/'outside.zip';external.write_bytes(stream.getvalue());path.symlink_to(external)
    with pytest.raises(OSError):update_helper.stage_upload(job)
    assert external.exists()
    path.unlink();os.link(external,path)
    with pytest.raises(ValueError):update_helper.stage_upload(job)
    assert external.exists()


def test_upload_permission_forward_only_and_helper_claim(setup,client,settings):
    admin,*_=setup
    private=Ed25519PrivateKey.generate()
    raw,key=bundle(key=private);settings.RELEASE_PUBLIC_KEY=key;settings.UPDATE_EXECUTION_ENABLED=True
    response=client.post('/api/updates/upload/',{'file':SimpleUploadedFile('release.zip',raw)},format='multipart')
    assert response.status_code==202
    job=UpdateUpload.objects.get();assert job.status=='pending'
    assert (settings.MEDIA_ROOT/'updates'/f'{job.id.hex}.zip').exists()
    # Concurrent upload is rejected before writing another file.
    assert client.post('/api/updates/upload/',{'file':SimpleUploadedFile('release.zip',raw)},format='multipart').status_code==400
    output=io.StringIO()
    with patch('sys.stdin',io.StringIO('{}')):call_command('update_job','claim_upload',stdout=output)
    assert json.loads(output.getvalue())['id']==str(job.id)
    settings.UPDATE_STATE.mkdir(parents=True)
    (settings.UPDATE_STATE/'offline-release.json').write_text(json.dumps({'version':'0.4.0','compatibility':{'signature':'Verified Ed25519'}}))
    with patch('sys.stdin',io.StringIO(json.dumps({'id':str(job.id)}))):call_command('update_job','upload_ready',stdout=io.StringIO())
    job.refresh_from_db();assert job.status=='ready'
    assert SystemSetting.objects.get(key='release_check').value['version']=='0.4.0'
    old,_=bundle(version='0.3.0',key=private)
    assert client.post('/api/updates/upload/',{'file':SimpleUploadedFile('old.zip',old)},format='multipart').status_code==400
    user=User.objects.create_user('no-updater');ordinary=APIClient();ordinary.force_authenticate(user)
    assert ordinary.post('/api/updates/upload/',{'file':SimpleUploadedFile('release.zip',raw)},format='multipart').status_code==403
