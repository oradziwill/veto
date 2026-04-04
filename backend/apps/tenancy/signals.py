from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.tenancy.models import Clinic

from .access import (
    SUPERUSER_CLINIC_IDS_CACHE_KEY,
    network_clinic_ids_cache_key,
)


def invalidate_clinic_access_list_caches(clinic: Clinic) -> None:
    cache.delete(SUPERUSER_CLINIC_IDS_CACHE_KEY)
    nets = {clinic.network_id}
    old = getattr(clinic, "_old_network_id", None)
    if old is not None:
        nets.add(old)
    nets.discard(None)
    for nid in nets:
        cache.delete(network_clinic_ids_cache_key(nid))


@receiver(pre_save, sender=Clinic)
def _clinic_stash_old_network_id(sender, instance: Clinic, **kwargs) -> None:
    if instance.pk:
        prev = Clinic.objects.filter(pk=instance.pk).values_list("network_id", flat=True).first()
        instance._old_network_id = prev  # type: ignore[attr-defined]
    else:
        instance._old_network_id = None  # type: ignore[attr-defined]


@receiver(post_save, sender=Clinic)
def _clinic_saved_invalidate_access_cache(sender, instance: Clinic, **kwargs) -> None:
    invalidate_clinic_access_list_caches(instance)


@receiver(post_delete, sender=Clinic)
def _clinic_deleted_invalidate_access_cache(sender, instance: Clinic, **kwargs) -> None:
    cache.delete(SUPERUSER_CLINIC_IDS_CACHE_KEY)
    if instance.network_id:
        cache.delete(network_clinic_ids_cache_key(instance.network_id))
