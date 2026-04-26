# accounts/mixins.py
from django.shortcuts import redirect
from django.urls import reverse


class SeriesAgeRequiredMixin:
    """
    Pulls `min_age` off the view’s object.series and
    blocks users under that age.
    """

    dob_entry_url = "enter-dob"  # name of your DOB‐capture view
    age_restricted_url = "age-restricted"  # name of your “sorry, too young” page

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # 1) Must be logged in
        if not user.is_authenticated:
            return redirect(f"{reverse('account_login')}?next={request.path}")

        # 2) Must have provided DOB
        if user.age is None:
            return redirect(reverse(self.dob_entry_url))

        # 3) Get the object (Episode or Series) and its series.min_age
        obj = self.get_object()
        if hasattr(obj, "series"):
            # If the object is an Episode, get the series from it
            series = obj.series
        else:
            # Otherwise, assume the object itself is a Series
            series = obj

        required = getattr(series, "min_age", None)

        # 4) If a min_age is set, enforce it
        if required is not None and user.age < required:
            return redirect(reverse(self.age_restricted_url))

        # 5) All good!
        return super().dispatch(request, *args, **kwargs)
