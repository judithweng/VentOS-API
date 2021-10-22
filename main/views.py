from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.core.serializers import serialize
from .models import PIRCS
from .forms import PostNewCommand
from django.views.decorators.csrf import csrf_exempt, csrf_protect

import time
import sys
import math
import json

# Create your views here.

most_recent_data_return_ms = time.time_ns() / 1000000
test_frequency_ms = 6000
sample_rate_ms = 25
MAX_SAMPLES = 1000
FLOW_RATE_ml_min = 18000

PIP_pressure_cmH2O = 20
Breaths_per_min = 10
Target_Flow_Rate_ml_per_s = 6000
MODE = 'P'

# This will be redone, but here I create a tiny
# "settings" state that we can manipulate with the PIRCS
# commands below, and the data response will depend on it.
# This is just a "hello, world" implementation now
def set_state_from_PIRCS(p):
    global PIP_pressure_cmH2O
    if (p.par == 'P' and p.int == 'T'):
        PIP_pressure_cmH2O = int(p.val/10)
        print("Set Pressure to:",file=sys.stderr)
        print(PIP_pressure_cmH2O,file=sys.stderr)
    elif (p.par == 'B' and p.int == 'T'):
        Breaths_per_min = int(p.val/10)
        print("Set Breaths Per Minute to:",file=sys.stderr)
        print(Breaths_per_min,file=sys.stderr)
    elif (p.par == 'F' and p.int == 'T'):
        Target_Flow_Rate_ml_per_s = int(p.val)
        print("Target Flow Rate:",file=sys.stderr)
        print(Target_Flow_Rate_ml_per_s,file=sys.stderr)
    elif (p.par == 'M'):
        MODE = p.int
        print("Mode Set To:",file=sys.stderr)
        print(MODE,file=sys.stderr)
    else:
        print("unknown par field",file=sys.stderr)
        print(p.par,file=sys.stderr)

def data(response, n):
    global most_recent_data_return_ms
    global PIP_pressure_cmH2O
    # return the first n data in the database
    # TODO
    # this is returning PIRCS, what we want is actually to return PIRDS

    ms = int(time.time_ns() / 1000000) # we want the time in ms


# Now I will create a returned set of sine waves for testing
# These will be "correct" in the since that they are tied to the epoch time.
# For now I will just create a pressure and flow wave out of phase.
# The pressure wave will be positive from 0 to 20cmH20.
# The flow wave will be both negative and positive (as if we are flowing
# out the same sensor we flowed in through)
    pirds_samples = []
    duration_ms = ms - most_recent_data_return_ms
    most_recent_data_return_ms = ms

    num_samples = int(min(duration_ms / sample_rate_ms, MAX_SAMPLES))
    start_sample_ms = ms - (num_samples * sample_rate_ms)

    for s in range(0,num_samples):
        current_sample_ms = start_sample_ms + s * sample_rate_ms
        p_mmH2O = int(PIP_pressure_cmH2O * 10 * math.sin(2 * math.pi * current_sample_ms / test_frequency_ms))
        f = int(FLOW_RATE_ml_min * math.sin((2 * math.pi * (current_sample_ms + test_frequency_ms/2) / test_frequency_ms)))
        p_pirds = { "event" : "M",
                    "type" : "D",
                    "loc" : "I",
                    "num" : 0,
                    'ms': current_sample_ms,
                    'val': p_mmH2O}
        f_pirds = { "event" : "M",
                    "type" : "F",
                    "loc" : "I",
                    "num" : 0,
                    'ms': current_sample_ms,
                    'val': f}
        pirds_samples.append(p_pirds)
        pirds_samples.append(f_pirds)

    json_object = json.dumps(pirds_samples, indent = 2)
    return HttpResponse(json_object, content_type="application/json")

@csrf_exempt
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
            set_state_from_PIRCS(p)
        else:
            print("Form Not Valid",file=sys.stderr)
            print(form.errors,file=sys.stderr)


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
