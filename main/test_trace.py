from .lung_sim import execute_scenario

# -----
# from Dr. Schulz's code
# https://github.com/ErichBSchulz/lung/blob/master/ventos/test_trace.py

sample_frequency = 20
time_resolution = round(1000/sample_frequency)

base_scenario = dict(
    title='Base',
    resistance=20,
    PEEP=5,
    IE=0.5,
    Pi=15,
    rate=10,
    end_time=30,
    time_resolution=time_resolution,  # ms between cycles
    flow_noise_sd=0.05,
    pressure_noise_sd=1,  # cmH2O
    heart_rate=85,
    cardiac_amplitude=0.05,
    events=[]
)

badnesses = dict(
    Creeping=[
        dict(attr='PEEP', val=7),
        dict(attr='PEEP', val=10, time=3),
        dict(attr='Pi', val=15, time=6),
        dict(attr='PEEP', val=14, time=10),
    ]
)

# factory for a list of scenarios
# uses and event record:
#     eg dict(attr = 'Pi', val = 15, time=start+6)


def scenarios(badnesses=badnesses,
              badness_start=40, fix=120,
              duration=240, sample_frequency=20):
    def add_new_events(current_events, new_events, offset, unwind_at=0, base=[]):
        for e in new_events:
            current_events.append(dict(e, time=e.get('time', 0)+offset))
        return unwind_badness(current_events,  new_events, unwind_at, base) if unwind_at else current_events
    # loop over daranged attributes and restore them

    def unwind_badness(current_events, badness, offset, base):
        for deranged in set([b['attr'] for b in badness]):
            current_events.append(
                dict(attr=deranged, val=base[deranged], time=offset))
        return current_events
    base = dict(base_scenario, time_resolution=round(1000/sample_frequency))
    scenarios = {}
    for title, badness in badnesses.items():
        scenarios[title] = dict(base,
                                title=title,
                                end_time=duration,
                                events=add_new_events([], new_events=badness, offset=badness_start, unwind_at=fix, base=base))
    return scenarios


def run_and_output(scenario):
    pdf = execute_scenario(scenario)
    # vent_plots(pdf, title=scenario['title'])
    # plt.show()
    return pdf
