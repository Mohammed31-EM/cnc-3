import os
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.files.base import ContentFile

from .models import Program, ProgramVersion

@receiver(pre_save, sender=Program)
def snapshot_program_file(sender, instance: Program, **kwargs):
    """
    Before saving a Program, if the file is being replaced,
    snapshot the OLD file into ProgramVersion.
    """
    if not instance.pk:
        return  # new Program — nothing to snapshot

    try:
        old = Program.objects.get(pk=instance.pk)
    except Program.DoesNotExist:
        return

    # If there was an old file and it changed
    if old.file and instance.file and old.file.name != instance.file.name:
        # Read old file bytes and save under a new name in program_versions/
        base = os.path.basename(old.file.name)
        with open(old.file.path, "rb") as fh:
            data = fh.read()
        ProgramVersion.objects.create(
            program=old,
            file=ContentFile(data, name=base),
            comment="Auto snapshot (pre-edit)",
        )