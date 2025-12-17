from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom User model for Easy Access Platform.

    Extends Django's AbstractUser to allow future customization.
    All authentication and permissions functionality is inherited.

    Future Extensions:
    - faculty: ForeignKey to Organization (which faculty user belongs to)
    - role: User role (admin, faculty_coordinator, viewer)
    - preferences: JSON field for UI preferences
    """

    # Currently using all default fields from AbstractUser:
    # username, first_name, last_name, email, is_staff, is_active, date_joined, etc.

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username
