"""The company is AK Builders (not AR Builders): fix the name and the number prefixes of
existing installs. Documents already issued keep their numbers; new ones start with AK/."""

from django.db import migrations


def forwards(apps, schema_editor):
    CompanySettings = apps.get_model("core", "CompanySettings")
    DocumentSequence = apps.get_model("core", "DocumentSequence")
    User = apps.get_model("accounts", "User")

    for c in CompanySettings.objects.filter(name__contains="AR Builders"):
        c.name = c.name.replace("AR Builders", "AK Builders")
        c.save(update_fields=["name"])
    for s in DocumentSequence.objects.all():
        if s.prefix == "AR" or s.prefix.startswith("AR/"):
            s.prefix = "AK" + s.prefix[2:]
            s.save(update_fields=["prefix"])
    User.objects.filter(username="admin", first_name="AR").update(first_name="AK")


def backwards(apps, schema_editor):
    pass  # nothing to undo safely


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_alter_auditlog_action"),
        ("accounts", "0001_initial"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
