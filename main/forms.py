from django import forms
from .models import Person


class PostNewCommand(forms.Form):
    com = forms.CharField(label="com", max_length=1)
    par = forms.CharField(label="par", max_length=1)
    int = forms.CharField(label="int", max_length=1)
    mod = forms.IntegerField(min_value=0, max_value=255)
    val = forms.FloatField()


class PersonForm(forms.Form):
    data = Person.objects.all()
    patients_choices = []

    for i in range(len(data)):
        patients_choice = (data[i].id, data[i])
        patients_choices.append(patients_choice)

    chosen_patient = forms.CharField(label='Choose a patient: ',
                                     widget=forms.Select(choices=patients_choices))
