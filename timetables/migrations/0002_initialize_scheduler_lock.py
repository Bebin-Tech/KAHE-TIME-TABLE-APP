from django.db import migrations


def initialize(apps, schema_editor):
    apps.get_model("timetables", "SchedulerLock").objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("timetables", "0001_initial")]
    operations = [migrations.RunPython(initialize, migrations.RunPython.noop)]
