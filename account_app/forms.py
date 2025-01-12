from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class myform(UserCreationForm):

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2") 

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class loginform(forms.Form):
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
