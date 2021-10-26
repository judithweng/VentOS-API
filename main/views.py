from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.core.serializers import serialize
from .models import PIRCS
from .forms import PostNewCommand
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from dataclasses import dataclass, asdict

import time
import sys
import math
import json
import pandas as pd
import matplotlib.pyplot as plt


most_recent_data_return_ms = time.time_ns() / 1000000
test_frequency_ms = 6000
sample_rate_ms = 25
MAX_SAMPLES = 1000
FLOW_RATE_ml_min = 18000

PIP_pressure_cmH2O = 20
Breaths_per_min = 10
Target_Flow_Rate_ml_per_s = 6000
MODE = 'P'

# ------


@dataclass
class VentilatorStatus:
    p: float = 0  # current pressure (cmH2O)
    vhigh: float = 0  # high pressure envelope
    vlow: float = 0  # low pressure envelope
    Vhigh: float = 0  # breath cycle maximum pressure
    Vlow: float = 0  # breath cycle minimum pressure
    Thigh: float = 0  # samples since most recent breath cycle maximum
    Tlow: float = 0  # samples since most recent breath cycle minimum
    Tpeak: float = 0  # samples since previous breath cycle maximmum
    PIP: float = 0  # smoothed peak inspriratory pressure
    PEEP: float = 0  # smoothed end expiratory pressure
    RR: float = 0  # respiratory rate (per minute)
    inhaling: bool = False


@dataclass
class VentilatorConfig:
    alphaA: float = 0.9  # envelope attack coefficient (0-1)
    alphaR: float = 0.99  # envelope release coefficient (0-1)
    alphaS: float = 0.9  # smoothing coefficient (0-1)
    alphaN: float = 0.9  # noise smoothing coefficient (0-1)
    sample_frequency: float = 10  # sample rate (Hz)
    # cmH2O - this value prevents noise triggering a breath
    min_breath_envelope_delta = 3

# generic smoothing function to apply return a weighted average of a new and old value
# alpha is between 0 and 1, the higher the alpha the slower the movement away


def recursive_smooth(alpha, current, new):
    return alpha * current + (1-alpha) * new


# config = config
# state = status - mutated by function
# p = latest pressure from pressure sensor
"""
Algorithm from https://arxiv.org/pdf/2006.03664.pdf
"""


def step(config, state, p):
    state.p = recursive_smooth(
        config.alphaN, state.p, p)  # store value in state
    state.Tpeak = state.Tpeak + 1
    if state.p >= state.vhigh:
        state.vhigh = recursive_smooth(config.alphaA, state.vhigh, state.p)
        state.Vhigh = state.p
        state.Thigh = 0
        if not state.inhaling and state.vhigh-state.vlow > config.min_breath_envelope_delta:
            state.inhaling = True
            state.PEEP = recursive_smooth(
                config.alphaS, state.PEEP, state.Vlow)
    else:
        state.vhigh = recursive_smooth(config.alphaR, state.vhigh, state.p)
        state.Thigh = state.Thigh + 1
    if state.p <= state.vlow:
        state.vlow = recursive_smooth(config.alphaA, state.vlow, state.p)
        state.Vlow = state.p
        state.Tlow = 0
        if state.inhaling:
            state.inhaling = False
            state.PIP = recursive_smooth(config.alphaS, state.PIP, state.Vhigh)
            if state.RR > 0:
                state.RR = 1 / recursive_smooth(config.alphaS, 1/state.RR,
                                                (state.Tpeak - state.Thigh) / (60 * config.sample_frequency))
            else:  # modification to prevent division by zero error
                state.RR = (60 * config.sample_frequency) / \
                    (state.Tpeak - state.Thigh)
            state.Tpeak = state.Thigh
    else:
        state.vlow = recursive_smooth(config.alphaR, state.vlow, state.p)
        state.Tlow = state.Tlow + 1

# ------


# This will be redone, but here I create a tiny
# "settings" state that we can manipulate with the PIRCS
# commands below, and the data response will depend on it.
# This is just a "hello, world" implementation now


def set_state_from_PIRCS(p):
    global PIP_pressure_cmH2O
    if (p.par == 'P' and p.int == 'T'):
        PIP_pressure_cmH2O = int(p.val/10)
        print("Set Pressure to:", file=sys.stderr)
        print(PIP_pressure_cmH2O, file=sys.stderr)
    elif (p.par == 'B' and p.int == 'T'):
        Breaths_per_min = int(p.val/10)
        print("Set Breaths Per Minute to:", file=sys.stderr)
        print(Breaths_per_min, file=sys.stderr)
    elif (p.par == 'F' and p.int == 'T'):
        Target_Flow_Rate_ml_per_s = int(p.val)
        print("Target Flow Rate:", file=sys.stderr)
        print(Target_Flow_Rate_ml_per_s, file=sys.stderr)
    elif (p.par == 'M'):
        MODE = p.int
        print("Mode Set To:", file=sys.stderr)
        print(MODE, file=sys.stderr)
    else:
        print("unknown par field", file=sys.stderr)
        print(p.par, file=sys.stderr)


@csrf_exempt
def data(response, n):
    global most_recent_data_return_ms
    global PIP_pressure_cmH2O

    ms = int(time.time_ns() / 1000000)  # we want the time in ms

    # temp_timestamps = []
    # temp_pressures = []
    # temp_flows = []

    vs = VentilatorStatus()
    config = VentilatorConfig()

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

    for s in range(0, num_samples):
        current_sample_ms = start_sample_ms + s * sample_rate_ms
        p_mmH2O = int(PIP_pressure_cmH2O * 10 * math.sin(2 *
                      math.pi * current_sample_ms / test_frequency_ms))
        f = int(FLOW_RATE_ml_min * math.sin((2 * math.pi *
                (current_sample_ms + test_frequency_ms/2) / test_frequency_ms)))

        # Call Step, take pressure and flow and put in PIRDS (from Dr. Schulz's code)
        step(config, vs, PIP_pressure_cmH2O)

        # temp_timestamps.append(current_sample_ms)
        # temp_pressures.append(p_mmH2O)
        # temp_flows.append(f)

        p_pirds = {"event": "M",
                   "type": "D",
                   "loc": "I",
                   "num": 0,
                   'ms': current_sample_ms,
                   'val': vs.p}

        # p_pirds = {"event": "M",
        #            "type": "D",
        #            "loc": "I",
        #            "num": 0,
        #            'ms': current_sample_ms,
        #            'val': p_mmH2O}
        f_pirds = {"event": "M",
                   "type": "F",
                   "loc": "I",
                   "num": 0,
                   'ms': current_sample_ms,
                   'val': f}
        pirds_samples.append(p_pirds)
        pirds_samples.append(f_pirds)

    json_object = json.dumps(pirds_samples, indent=2)
    response = HttpResponse(json_object, content_type="application/json")
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response["Access-Control-Max-Age"] = "1000"
    response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"

    # temp_graph_df = pd.DataFrame(list(zip(
    #     temp_timestamps, temp_pressures, temp_flows)), columns=['time', 'pressure', 'flow'])

    # print(temp_graph_df)

    # temp_graph_df.plot(x='time', y=['pressure', 'flow'])
    # plt.show()

    return response

    # return temp_graph_df


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
            print("Form Not Valid", file=sys.stderr)
            print(form.errors, file=sys.stderr)

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
