from django import forms


class PostNewCommand(forms.Form):
    com = forms.CharField(label="com", max_length=1)
    par = forms.CharField(label="par", max_length=1)
    int = forms.CharField(label="int", max_length=1)
    mod = forms.IntegerField(min_value=0, max_value=255)
    val = forms.IntegerField()
