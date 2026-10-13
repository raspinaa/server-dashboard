"""Inventory reports: scoped aggregates; disk joins never multiply CPU/RAM totals."""
from datetime import timedelta
from django.db.models import Count, Sum, Q
from django.utils import timezone
from .models import Machine, Disk, Activity, Project, Environment


def management_report(projects, project=None, environment=None, page=1):
    projects = projects.filter(archived=False)
    if project is not None:
        projects = projects.filter(pk=project.pk)
    rows = Machine.objects.filter(project__in=projects, archived=False)
    if environment is not None:
        rows = rows.filter(environment=environment)

    def totals(query):
        values = query.aggregate(machines=Count('id'), cpu=Sum('cpu'), ram=Sum('ram'))
        return {'machines': values['machines'], 'cpu': values['cpu'] or 0,
                'ram': str(values['ram'] or 0),
                'disk': str(Disk.objects.filter(machine__in=query).aggregate(value=Sum('size'))['value'] or 0)}

    def groups(*dimensions):
        grouped = rows.values(*dimensions).annotate(machines=Count('id'), cpu=Sum('cpu'), ram=Sum('ram')).order_by(*dimensions)
        disk_dimensions = ['machine__' + name for name in dimensions]
        capacities = {tuple(row[key] for key in disk_dimensions): row['size'] for row in
                      Disk.objects.filter(machine__in=rows).values(*disk_dimensions).annotate(size=Sum('size'))}
        return [{**row, 'ram': str(row['ram'] or 0), 'disk': str(capacities.get(tuple(row[key] for key in dimensions), 0))} for row in grouped]

    machine_count = rows.count()
    page_count = max(1, (machine_count + 49) // 50)
    if page < 1 or page > page_count:
        from rest_framework.exceptions import ValidationError
        raise ValidationError("صفحه گزارش نامعتبر است")
    details = []
    for machine in rows.select_related('project','environment','application').prefetch_related('disks').order_by('project_id','server_name','id')[(page-1)*50:page*50]:
        details.append({'id': str(machine.id), 'project_name': machine.project.name,
                        'environment_name': machine.environment.name,
                        'application': machine.application.name if machine.application else '',
                        **{name: getattr(machine, name) for name in ('server_name','vms','cpu','ram','os','network','ip','subnet','gateway','username','status')},
                        'disks': [{'name': disk.name, 'size': str(disk.size)} for disk in machine.disks.all()]})

    now = timezone.now()
    activity = Activity.objects.filter(machine__in=rows, created_at__gte=now-timedelta(days=30))
    return {
        'generated_at': now, 'machines': details, 'page': page, 'pages': page_count, 'scope': 'selected_project' if project else 'accessible_projects',
        'totals': totals(rows), 'project_count': projects.count(),
        'environment_count': Environment.objects.filter(project__in=projects, archived=False, **({'pk': environment.pk} if environment else {})).count(),
        'projects': groups('project_id', 'project__name'),
        'environments': groups('project__name', 'environment_id', 'environment__name'),
        'services': groups('project__name', 'application_id', 'application__name'),
        'operating_systems': groups('os'), 'networks': groups('project__name', 'environment__name', 'network'),
        'statuses': list(rows.values('status').annotate(machines=Count('id')).order_by('status')),
        'quality': {'missing_ip': rows.filter(ip='').count(), 'missing_subnet': rows.filter(subnet='').count(),
                    'missing_os': rows.filter(os='').count(), 'missing_application': rows.filter(application=None).count(),
                    'without_disks': rows.filter(disks__isnull=True).count(),
                    'zero_resources': rows.filter(Q(cpu=0)|Q(ram=0)).count(),
                    'duplicate_ip_contexts': rows.exclude(ip='').values('project_id','environment_id','network','ip').annotate(n=Count('id')).filter(n__gt=1).count()},
        'activity_30_days': list(activity.values('event','source').annotate(count=Count('id')).order_by('event','source')),
        'disk_count': Disk.objects.filter(machine__in=rows).count(),
    }
