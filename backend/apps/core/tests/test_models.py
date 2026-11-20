import pytest
from django.core.management import call_command
from django.db import IntegrityError

from apps.accounts.models import Role, User
from apps.core.models import AuditLog
from apps.customers.models import Customer
from apps.materials.models import Material


@pytest.mark.django_db
def test_soft_delete_hides_row_and_is_audited():
    c = Customer.objects.create(name="Ravi Kumar", phone="9876543210")
    c.soft_delete()
    assert not Customer.objects.filter(pk=c.pk).exists()
    assert Customer.all_objects.filter(pk=c.pk, is_deleted=True).exists()
    actions = list(AuditLog.objects.filter(object_id=str(c.pk)).values_list("action", flat=True))
    assert "CREATE" in actions and "DELETE" in actions


@pytest.mark.django_db
def test_seed_data_is_idempotent():
    call_command("seed_data")
    call_command("seed_data")
    assert Role.objects.count() == 5
    assert User.objects.filter(username="admin").count() == 1
    assert Material.objects.filter(name__startswith="TMT Rod").count() == 4


@pytest.mark.django_db
def test_stock_cannot_go_negative_at_db_level():
    call_command("seed_data")
    m = Material.objects.first()
    m.stock_quantity = -1
    with pytest.raises(IntegrityError):
        m.save()
