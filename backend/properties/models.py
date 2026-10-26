"""Properties and rentable spaces. Every row carries the workspace id."""

from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from properties.validation import block_pair_error


class Property(models.Model):
    """A building site or address that belongs to one workspace."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="properties",
    )
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "workspace",
                name="prop_property_name_ci",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a property name."})
        self.address = self.address.strip()

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Building(models.Model):
    """Optional grouping inside a property. A property does not need one."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="buildings",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="buildings",
    )
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "property",
                name="prop_building_name_ci",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a building name."})
        if self.property.workspace_id != self.workspace_id:
            raise ValidationError({"property": "Choose a property in this workspace."})

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Floor(models.Model):
    """Optional floor. It can belong to a building or sit on the property."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="floors",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="floors",
    )
    building = models.ForeignKey(
        Building,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="floors",
    )
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "property",
                "building",
                name="prop_floor_place_name",
                nulls_distinct=False,
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a floor name."})
        if self.property.workspace_id != self.workspace_id:
            raise ValidationError({"property": "Choose a property in this workspace."})
        if self.building_id is not None:
            building = self.building
            if building is None:
                raise ValidationError(
                    {"building": "Choose a building on this property."}
                )
            if building.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"building": "Choose a building in this workspace."}
                )
            if building.property_id != self.property_id:
                raise ValidationError(
                    {"building": "Choose a building on this property."}
                )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Space(models.Model):
    """A rentable whole unit or room. A unit is not required to have beds."""

    class Kind(models.TextChoices):
        UNIT = "unit", "Whole unit"
        ROOM = "room", "Room"

    class Availability(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        UNAVAILABLE = "unavailable", "Unavailable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="spaces",
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="spaces",
    )
    building = models.ForeignKey(
        Building,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="spaces",
    )
    floor = models.ForeignKey(
        Floor,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="spaces",
    )
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    availability = models.CharField(
        max_length=16,
        choices=Availability.choices,
        default=Availability.ACTIVE,
    )
    block_reason = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=(
            "Empty, or maintenance when availability is unavailable. "
            "Unavailable plus maintenance is the maintenance block."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "property",
                "building",
                "floor",
                name="prop_space_place_name",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["unit", "room"]),
                name="prop_space_kind_known",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    availability__in=["active", "inactive", "unavailable"]
                ),
                name="prop_space_avail_known",
            ),
            models.CheckConstraint(
                condition=models.Q(block_reason__in=["", "maintenance"]),
                name="prop_space_block_known",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(availability="unavailable") | models.Q(block_reason="")
                ),
                name="prop_space_block_match",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a name."})
        if self.kind not in self.Kind.values:
            raise ValidationError({"kind": "Choose a whole unit or a room."})
        error = block_pair_error(self.availability, self.block_reason)
        if error:
            raise ValidationError(error)
        if self.property.workspace_id != self.workspace_id:
            raise ValidationError({"property": "Choose a property in this workspace."})
        if self.building_id is not None:
            building = self.building
            if building is None:
                raise ValidationError(
                    {"building": "Choose a building on this property."}
                )
            if building.workspace_id != self.workspace_id:
                raise ValidationError(
                    {"building": "Choose a building in this workspace."}
                )
            if building.property_id != self.property_id:
                raise ValidationError(
                    {"building": "Choose a building on this property."}
                )
        if self.floor_id is not None:
            floor = self.floor
            if floor is None:
                raise ValidationError({"floor": "Choose a floor on this property."})
            if floor.workspace_id != self.workspace_id:
                raise ValidationError({"floor": "Choose a floor in this workspace."})
            if floor.property_id != self.property_id:
                raise ValidationError({"floor": "Choose a floor on this property."})
            if floor.building_id != self.building_id:
                raise ValidationError(
                    {"floor": "Choose a floor in the selected building."}
                )
        if (
            self.kind == self.Kind.UNIT
            and self.pk
            and not self._state.adding
            and Bed.objects.filter(space_id=self.pk).exists()
        ):
            raise ValidationError(
                {"kind": ("Remove the beds before marking this space as a whole unit.")}
            )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)


class Bed(models.Model):
    """Optional bed inside a room. Whole units do not have beds."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "organizations.Workspace",
        on_delete=models.CASCADE,
        related_name="beds",
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="beds",
    )
    name = models.CharField(max_length=200)
    availability = models.CharField(
        max_length=16,
        choices=Space.Availability.choices,
        default=Space.Availability.ACTIVE,
    )
    block_reason = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "space",
                name="prop_bed_space_name",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    availability__in=["active", "inactive", "unavailable"]
                ),
                name="prop_bed_avail_known",
            ),
            models.CheckConstraint(
                condition=models.Q(block_reason__in=["", "maintenance"]),
                name="prop_bed_block_known",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(availability="unavailable") | models.Q(block_reason="")
                ),
                name="prop_bed_block_match",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a bed name."})
        error = block_pair_error(self.availability, self.block_reason)
        if error:
            raise ValidationError(error)
        if self.space.workspace_id != self.workspace_id:
            raise ValidationError({"space": "Choose a room in this workspace."})
        if self.space.kind != Space.Kind.ROOM:
            raise ValidationError(
                {"space": ("Beds belong to a room. A whole unit does not have beds.")}
            )

    def save(self, **kwargs: Any) -> None:
        self.full_clean()
        super().save(**kwargs)
