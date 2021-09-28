from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.core.serializers import serialize
from .models import PIRCS
from .forms import PostNewCommand

# Create your views here.


def data(response, n):
    # return the first n data in the database
    # TODO
    # this is returning PIRCS, what we want is actually to return PIRDS

    data = PIRCS.objects.all()[:(n+1)]
    data_json = serialize("json", data)

    return HttpResponse(data_json, content_type="application/json")


def control(response):
    if response.method == "POST":
        form = PostNewCommand(response.POST)
        succeed = False

        if form.is_valid():
            com = form.cleaned_data["com"]
            par = form.cleaned_data["par"]
            int = form.cleaned_data["int"]
            mod = form.cleaned_data["mod"]
            val = form.cleaned_data["val"]

            p = PIRCS(com=com, par=par, int=int, mod=mod, val=val)
            p.save()
            succeed = True

        data = PIRCS.objects.last()

        data_py = serialize("python", [data, ])
        data_py[-1]["fields"]["ack"] = "S"
        data_py[-1]["fields"]["err"] = 0

        if not succeed:
            data_py[-1]["fields"]["ack"] = "X"

        return JsonResponse(data_py, safe=False)

    else:
        form = PostNewCommand()

    return render(response, "main/control.html", {"form": form})
