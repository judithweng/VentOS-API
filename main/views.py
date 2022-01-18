from django.http.response import JsonResponse
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.serializers import serialize
from .models import PIRCS, PatientState, VentilatorState, Person, Session
from .forms import PostNewCommand, PersonForm
from django.views.decorators.csrf import csrf_exempt
from .lung_sim import Patient, Ventilator

import time
import sys
import json
import matplotlib.pyplot as plt

most_recent_data_return_ms = time.time_ns() / 1000000
test_frequency_ms = 6000
sample_rate_ms = 25
MAX_SAMPLES = 1000
FLOW_RATE_ml_min = 18000

PIP_pressure_cmH2O = 20
Breaths_per_min = 10
Target_Flow_Rate_ml_per_s = 6000
PEEP = 5
IE = 0.5
MODE = 'P'

pid = Person.objects.first().id
sid = None

# This will be redone, but here I create a tiny
# "settings" state that we can manipulate with the PIRCS
# commands below, and the data response will depend on it.
# This is just a "hello, world" implementation now


def set_state_from_PIRCS(p):
    global PIP_pressure_cmH2O
    global Target_Flow_Rate_ml_per_s
    global ventilator
    global patient

    if (p.par == 'P' and p.int == 'T'):
        PIP_pressure_cmH2O = int(p.val/10)
        # Warning: This needst to be cleand up
        ventilator.Pi = PIP_pressure_cmH2O
        print("Set Pressure to:", file=sys.stderr)
        print(PIP_pressure_cmH2O, file=sys.stderr)

    elif (p.par == 'B' and p.int == 'T'):
        Breaths_per_min = int(p.val/10)
        # Warning: This needst to be cleand up
        ventilator.rate = Breaths_per_min
        print("Set Breaths Per Minute to:", file=sys.stderr)
        print(Breaths_per_min, file=sys.stderr)

    elif (p.par == 'I' and p.int == 'T'):
        IE = 1 / (p.val / 10)
        # Warning: This needst to be cleand up
        ventilator.IE = IE
        print("Set IE ratio to to:", file=sys.stderr)
        print(IE, file=sys.stderr)

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


def set_patient_state():
    global patient
    global pid
    global ventilator
    global sid

    patient_data = Person.objects.all()
    chosen_patient = patient_data.filter(id=pid)
    chosen_patient = chosen_patient[0]
    ms = int(time.time_ns() / 1000000)

    # since we filter using unique id, this is guaranteed to be at max 1, so [0] is used
    patient.weight = chosen_patient.weight
    patient.height = chosen_patient.height
    patient.sex = chosen_patient.sex
    patient.resistance = chosen_patient.resistance
    # compliance = chosen_patient[0].compliance

    print("Patient state is set. Height: " + str(patient.height) + "cm, weight: " + str(patient.weight) +
          " kg, sex: " + patient.sex + ", resistance: " + str(patient.resistance))
    #    + ", compliance: " + str(compliance))

    # set up model instances
    # create a new session and save current settings to session
    # default PIRCS settings
    # TODO: changed default PIRCS setting
    curr_session = Session(person=chosen_patient)
    curr_session.save()
    sid = curr_session.id
    print("CURRENT SESSION ID: " + str(sid))

    curr_pircs = PIRCS(com="C", par="P", int="T", mod=0,
                       val=250, session=curr_session)
    curr_pircs.save()

    curr_patient_state = PatientState(timestamp=ms, TLC=patient.TLC,
                                      pressure_mouth=patient.pressure_mouth, resistance=patient.resistance,
                                      pressure_alveolus=patient.pressure_alveolus, lung_volume=patient.lung_volume,
                                      pressure_intrapleural=patient.pressure_intrapleural, flow=patient.flow, log=patient.log,
                                      session=curr_session)
    curr_patient_state.save()

    curr_ventilator_state = VentilatorState(timestamp=ms, pressure=ventilator.pressure, pressure_mouth=ventilator.pressure_mouth,
                                            mode=ventilator.mode, Pi=ventilator.Pi, PEEP=ventilator.PEEP, rate=ventilator.rate,
                                            IE=ventilator.IE, phase=ventilator.phase, log=ventilator.log, session=curr_session)
    curr_ventilator_state.save()


# Global patient and ventilator state
patient = Patient()
ventilator = Ventilator("PCV", PIP_pressure_cmH2O, PEEP, Breaths_per_min, IE)


@csrf_exempt
def data(response, n):
    global most_recent_data_return_ms
    global PIP_pressure_cmH2O
    global Target_Flow_Rate_ml_per_s
    global patient
    global ventilator

    # print("PATIENT LOG")
    # print(patient.log)
    # print("VENTILATOR LOG")
    # print(ventilator.log)

    ms = int(time.time_ns() / 1000000)  # we want the time in ms
    patient_status = patient.status()

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
    num_samples = min(num_samples, n)
    start_sample_ms = ms - (num_samples * sample_rate_ms)

    for current_sample_ms in range(start_sample_ms, ms, sample_rate_ms):
        ventilator_status = ventilator.advance(
            advance_time=sample_rate_ms, pressure_mouth=patient_status["pressure_mouth"])
        patient_status = patient.advance(
            advance_time=sample_rate_ms, pressure_mouth=ventilator_status["pressure_mouth"])

        p_mmH2O = patient_status["pressure_mouth"]*10
        f = patient_status["flow"]*10

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

    json_object = json.dumps(pirds_samples, indent=2)
    response = HttpResponse(json_object, content_type="application/json")
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response["Access-Control-Max-Age"] = "1000"
    response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"

    return response


@csrf_exempt
def patient_info(response):
    global pid

    data = Person.objects.all()
    patients_data = []

    for d in data:
        patient_data = {}
        patient_data['id'] = str(d.id)
        patient_data['name'] = d.name
        patient_data['weight'] = d.weight
        patient_data['height'] = d.height
        patient_data['sex'] = d.sex
        patient_data['resistance'] = d.resistance
        patient_data['compliance'] = d.compliance
        patients_data.append(patient_data)

    json_object = json.dumps(patients_data, indent=2)
    response = HttpResponse(json_object, content_type="application/json")
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response["Access-Control-Max-Age"] = "1000"
    response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"

    return response


@csrf_exempt
def control(response):
    global sid
    global patient
    global ventilator

    ms = int(time.time_ns() / 1000000)

    if response.method == "POST":
        form = PostNewCommand(response.POST)
        succeed = False
        if form.is_valid():
            fcom = form.cleaned_data["com"]
            fpar = form.cleaned_data["par"]
            fint = form.cleaned_data["int"]
            fmod = form.cleaned_data["mod"]
            fval = form.cleaned_data["val"]

            # get a new PIRCS setting from vent-display
            # fetch latest session, use previous PIRCS setting to advance until current timestamp
            session = Session.objects.all().filter(id=sid)
            session = session[0]
            patState = PatientState.objects.all().filter(session=session)
            patState = patState[0]
            ventState = VentilatorState.objects.all().filter(session=session)
            ventState = ventState[0]

            prev_timestamp = patState.timestamp

            print("need to advance: " + str(ms-prev_timestamp) + " ms.")

            ventilator_status = ventilator.advance(
                advance_time=ms-prev_timestamp, pressure_mouth=patState.pressure_mouth)
            patient_status = patient.advance(
                advance_time=ms-prev_timestamp, pressure_mouth=ventState.pressure_mouth)

            curr_patient_state = PatientState(timestamp=ms, TLC=patient.TLC,
                                              pressure_mouth=patient.pressure_mouth, resistance=patient.resistance,
                                              pressure_alveolus=patient.pressure_alveolus, lung_volume=patient.lung_volume,
                                              pressure_intrapleural=patient.pressure_intrapleural, flow=patient.flow, log=patient.log,
                                              session=session)
            curr_patient_state.save()

            curr_ventilator_state = VentilatorState(timestamp=ms, pressure=ventilator.pressure, pressure_mouth=ventilator.pressure_mouth,
                                                    mode=ventilator.mode, Pi=ventilator.Pi, PEEP=ventilator.PEEP, rate=ventilator.rate,
                                                    IE=ventilator.IE, phase=ventilator.phase, log=ventilator.log, session=session)
            curr_ventilator_state.save()

            # save with the new PIRCS setting
            p = PIRCS(com=fcom, par=fpar, int=fint,
                      mod=fmod, val=fval, session=session)
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


@csrf_exempt
def home(response):
    global pid

    if response.method == "POST":
        form = PersonForm(response.POST)

        if form.is_valid():
            # get the id of the patient
            pid = form.cleaned_data["chosen_patient"]
            set_patient_state()

    else:
        form = PersonForm()

    return render(response, "main/home.html", {"form": form})
