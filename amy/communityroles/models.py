from datetime import date

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse

from fiscal.models import Membership
from workshops.mixins import CreatedUpdatedMixin
from workshops.models import Award, Badge, Person


class CommunityRoleConfig(CreatedUpdatedMixin, models.Model):
    name = models.CharField(max_length=150)
    display_name = models.CharField(max_length=150)
    link_to_award = models.BooleanField("Should link to an Award?")
    award_badge_limit = models.ForeignKey(
        Badge,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    link_to_membership = models.BooleanField("Should link to a Membership?")
    additional_url = models.BooleanField("Should allow for additional URL?")
    generic_relation_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return self.display_name


class CommunityRoleInactivation(CreatedUpdatedMixin, models.Model):
    name = models.CharField(max_length=150)

    def __str__(self) -> str:
        return self.name


class CommunityRole(CreatedUpdatedMixin, models.Model):
    config = models.ForeignKey(CommunityRoleConfig, on_delete=models.PROTECT)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    award = models.ForeignKey(Award, on_delete=models.PROTECT, null=True, blank=True)
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)
    inactivation = models.ForeignKey(
        CommunityRoleInactivation, on_delete=models.PROTECT, null=True, blank=True
    )
    membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, null=True, blank=True
    )
    url = models.URLField("URL", blank=True, default="")

    # value should be copied from related `CommunityRoleConfig`
    generic_relation_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    generic_relation_pk = models.PositiveIntegerField(null=True, blank=True)
    generic_relation = GenericForeignKey(
        "generic_relation_content_type", "generic_relation_pk"
    )

    def __str__(self) -> str:
        return f'Community Role "{self.config}" for {self.person}'

    def get_absolute_url(self):
        return reverse("communityrole_details", kwargs={"pk": self.pk})

    def is_active(self) -> bool:
        """Determine if a community role is considered active.

        Rules for INACTIVE:
        1. `inactivation` is provided, or...
        2. End is provided and it's <= today, or...
        3. Start is provided and it's > today, or...
        4. Both start and end are provided, and today is NOT between them.

        Otherwise by default it's ACTIVE."""
        today = date.today()
        if (
            self.inactivation is not None
            or (self.end and self.end <= today)
            or (self.start and self.start > today)
            or (self.start and self.end and not (self.start <= today < self.end))
        ):
            return False
        return True
