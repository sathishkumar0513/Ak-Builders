from celery import shared_task

from .services import expire_due_quotations


@shared_task
def expire_quotations():
    """Daily: mark sent quotations past their validity date as EXPIRED."""
    return expire_due_quotations()
