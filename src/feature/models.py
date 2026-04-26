from django.core.validators import RegexValidator
from django.db import models


# Model to represent a feature
class FeatureFlag(models.Model):

    class TypeChoices(models.IntegerChoices):
        BOOLEAN = 1, "Boolean"
        STRING = 2, "String"
        INTEGER = 3, "Integer"

    key = models.CharField(
        max_length=255,
        unique=True,
        help_text="This should always be a camelCase string.",
        validators=[
            RegexValidator(
                regex=r"^[a-z]+(?:[A-Z][a-z0-9]*)*$",
                message="Key must be a camelCase string.",
            )
        ],
    )
    site = models.ForeignKey("sites.Site", on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    value = models.CharField(max_length=255)
    type = models.IntegerField(
        choices=TypeChoices.choices,
        help_text="The data type of the feature flag used by the serializer.",
    )
    permissions = models.ManyToManyField(
        "auth.Permission", help_text="Permissions associated with this feature"
    )  # Permissions associated with this feature.  If none, it is accessible to all users.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

    class Meta:
        permissions = [
            ("can_develop_features", "Can develop features (developer)"),
            ("can_alpha_test_features", "Can alpha test features"),
            ("can_beta_test_features", "Can beta test features"),
        ]
