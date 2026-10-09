from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Feedback, Complaint


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={"autofocus": True, "class": "form-control"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(
                choices=[(i, f"{i} star{'s' if i != 1 else ''}") for i in range(1, 6)],
                attrs={"class": "form-select"},
            ),
            "comment": forms.Textarea(attrs={
                "rows": 4, "class": "form-control",
                "placeholder": "What did you think of this tutorial?",
            }),
        }


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["description"]
        widgets = {
            "description": forms.Textarea(attrs={
                "rows": 4, "class": "form-control",
                "placeholder": "Describe the issue (e.g. poor audio, lecturer was late)...",
            }),
        }


class ClaimRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Reason for rejection",
        required=True,
    )
