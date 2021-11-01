from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.http import HttpResponse
from django.core.serializers import serialize
from .models import PIRCS
from .forms import PostNewCommand
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from dataclasses import dataclass, asdict
from pynverse import inversefunc

import time
import sys
import math
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import collections


most_recent_data_return_ms = time.time_ns() / 1000000
test_frequency_ms = 6000
sample_rate_ms = 25
MAX_SAMPLES = 1000
FLOW_RATE_ml_min = 18000

PIP_pressure_cmH2O = 20
Breaths_per_min = 10
Target_Flow_Rate_ml_per_s = 6000
MODE = 'P'


# -----
# from Dr. Schulz's code
# https://github.com/ErichBSchulz/lung/blob/master/ventos/lung.py
# https://github.com/ErichBSchulz/lung/blob/master/ventos/sim/simple.py

# a set of three bi-directional lung and chest wall curves allowing calculation
# of pressure from volume, and volume from pressure
# exports both simple and vectorized forms

# see https://docs.google.com/spreadsheets/d/1BO59dnA8dqs8TdPTD3WMBnii7FRxPDB1FVFzTB6eVsU/edit?usp=sharing for curves

def lung(p):
    return 6.66 + 27.9 * math.log(p if p > 0 else 0.000000001)


def chest_wall(p):
    return 51.3 * math.exp(0.0635 * p)


def total(p):
    b = 46.2134
    a = -261.437
    c = -9.68139
    d = 11.6401
    f = 1.2952
    return b + c * math.sin((p+a)/d) + f * p


switch_v_p = {"Total": total,
              "Lung": lung,
              "Chest": chest_wall}
switch_p_v = {"Total": inversefunc(total),
              "Lung": inversefunc(lung),
              "Chest": inversefunc(chest_wall)}


def asscalar(x):
    is_list = hasattr(x, "item")  # isinstance(x, list)
    return x.item() if is_list else x


# report volumes as % of total TLC
def volume_from_pressure(p, type="Total"):
    func = switch_v_p.get(type, lambda: 'error bad type')
    return asscalar(func(p))


def pressure_from_volume(v, type="Total"):
    func = switch_p_v.get(type, lambda: 'error bad type')
    return asscalar(func(v))


# setting up Patient
Patient_log = collections.namedtuple(
    'Patient_log',
    ['time', 'pressure_mouth', 'pressure_alveolus', 'pressure_intrapleural', 'lung_volume', 'flow'])


class Patient:
    def __init__(self,
                 height=175,  # cm
                 weight=70,  # kg
                 sex='M',  # M or other
                 pressure_mouth=0,  # cmH2O
                 resistance=10  # cmh2o/l/s or cmh2o per ml/ms
                 ):
        self.time = 0  # miliseconds
        self.height = height
        self.weight = weight
        self.sex = sex
        self.TLC = 6000 if sex == 'M' else 4200  # todo calculate on age, height weight
        self.pressure_mouth = pressure_mouth
        self.resistance = resistance
        self.pressure_alveolus = pressure_mouth  # start at equlibrium
        v_percent = volume_from_pressure(
            self.pressure_alveolus, 'Total')  # assuming no resp effort
        self.lung_volume = self.TLC * v_percent / 100
        self.pressure_intrapleural = pressure_from_volume(v_percent, 'Chest')
        self.flow = 0
        self.log = []

    def status(self):
        return Patient_log(self.time, self.pressure_mouth, self.pressure_alveolus, self.pressure_intrapleural, self.lung_volume, self.flow)

    def advance(self, advance_time=200, pressure_mouth=0):
        self.time = self.time + advance_time  # miliseconds
        self.pressure_mouth = pressure_mouth
        gradient = pressure_mouth - self.pressure_alveolus
        self.flow = gradient / self.resistance  # l/second or ml/ms
        self.lung_volume += self.flow * advance_time
        v_percent = self.lung_volume * 100 / self.TLC
        self.pressure_alveolus = pressure_from_volume(v_percent, "Total")
        self.pressure_intrapleural = pressure_from_volume(v_percent, "Chest")
        status = self.status()
        self.log.append(status)
        return status


# setting up Ventilator
Ventilator_log = collections.namedtuple(
    'Ventilator_log', ['time', 'phase', 'pressure', 'pressure_mouth'])


class Ventilator:
    def __init__(self, mode="PCV", Pi=15, PEEP=5, rate=10, IE=0.5):
        self.pressure = 0
        self.pressure_mouth = 0
        self.mode = mode
        self.Pi = Pi
        self.PEEP = PEEP
        self.rate = rate
        self.IE = IE
        self.phase = "E"
        self.log = []
        self.time = 0  # miliseconds

    def target_pressure(self):
        return self.PEEP if self.phase == "E" else self.Pi

    def status(self):
        return Ventilator_log(self.time, self.phase, self.pressure, self.pressure_mouth)

    def advance(self, advance_time=200, pressure_mouth=0):
        self.time = self.time + advance_time  # miliseconds
        self.pressure_mouth = pressure_mouth  # cmH2O
        # set phase
        breath_length = 60000 / self.rate  # milliseconds
        time_since_inspiration_began = self.time % breath_length
        inspiration_length = breath_length * self.IE / (self.IE + 1)
        new_phase = "I" if time_since_inspiration_began < inspiration_length else "E"
        if new_phase != self.phase:
            self.phase = new_phase
            self.pressure = self.target_pressure()
            self.pressure_mouth = self.pressure  # assume perfect ventilator
        status = self.status()
        self.log.append(status)
        return status


def loop(patient, ventilator,
         start_time=0, end_time=20000, time_resolution=50):
    # print('starting', patient.status())
    patient_status = patient.advance(advance_time=0)
    # print('vent starting', ventilator.status())
    for current_time in range(start_time, end_time, time_resolution):
        ventilator_status = ventilator.advance(
            advance_time=time_resolution, pressure_mouth=patient_status.pressure_mouth)
        patient_status = patient.advance(
            advance_time=time_resolution, pressure_mouth=ventilator_status.pressure_mouth)

        # if len(events) and events[0]['time']*1000 <= current_time:
        #     e = events.pop(0)
        #     print(
        #         f'Event at {current_time}ms setting {e["attr"]} to {e["val"]}')
        #     setattr(ventilator, e["attr"], e["val"])

    df = pd.DataFrame.from_records(patient.log, columns=Patient_log._fields)

    # if len(events):
    #     print(f'WARNING {len(events)} unprocessed')

    return df
# -----


# This will be redone, but here I create a tiny
# "settings" state that we can manipulate with the PIRCS
# commands below, and the data response will depend on it.
# This is just a "hello, world" implementation now


def set_state_from_PIRCS(p):
    global PIP_pressure_cmH2O
    global Target_Flow_Rate_ml_per_s

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
    global Target_Flow_Rate_ml_per_s

    ms = int(time.time_ns() / 1000000)  # we want the time in ms

    patient = Patient(pressure_mouth=PIP_pressure_cmH2O)
    ventilator = Ventilator(PEEP=PIP_pressure_cmH2O,
                            rate=Target_Flow_Rate_ml_per_s)

    patient_status = patient.advance(advance_time=most_recent_data_return_ms)

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

    for current_sample_ms in range(start_sample_ms, ms, sample_rate_ms):
        ventilator_status = ventilator.advance(
            advance_time=sample_rate_ms, pressure_mouth=patient_status.pressure_mouth)
        patient_status = patient.advance(
            advance_time=sample_rate_ms, pressure_mouth=ventilator_status.pressure_mouth)

        p_mmH2O = patient_status.pressure_mouth
        f = patient_status.flow

        # p_mmH2O = int(PIP_pressure_cmH2O * 10 * math.sin(2 *
        #               math.pi * current_sample_ms / test_frequency_ms))
        # f = int(FLOW_RATE_ml_min * math.sin((2 * math.pi *
        #         (current_sample_ms + test_frequency_ms/2) / test_frequency_ms)))

        # temp_timestamps.append(current_sample_ms)
        # temp_pressures.append(p_mmH2O)
        # temp_flows.append(f)

        # p_pirds = {"event": "M",
        #            "type": "D",
        #            "loc": "I",
        #            "num": 0,
        #            'ms': current_sample_ms,
        #            'val': vs.p}

        p_pirds = {"event": "M",
                   "type": "D",
                   "loc": "I",
                   "num": 0,
                   'ms': current_sample_ms,
                   'val': p_mmH2O}
        f_pirds = {"event": "M",
                   "type": "F",
                   "loc": "I",
                   "num": 0,
                   'ms': current_sample_ms,
                   'val': f}
        pirds_samples.append(p_pirds)
        pirds_samples.append(f_pirds)

    # df = pd.DataFrame.from_records(
    #     patient.log, columns=Patient_log._fields)

    # print(df)

    # pirds = df_to_PIRDS(df)

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
