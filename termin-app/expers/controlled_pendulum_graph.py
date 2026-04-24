#!/usr/bin/env python3

import rxsignal
import rxsignal.rxmqtt
import time
import rxsignal.flowchart
import matplotlib.pyplot as plt
import pickle

#chart = rxsignal.flowchart.FlowChart()

torques = []
torques_time = []

start_time = time.time()

mqttclient = rxsignal.rxmqtt.mqtt_rxclient()

def worker(data):
    torques.append(data)
    torques_time.append(time.time() - start_time)
     
mqttclient.subscribe("pendulum/torque", worker)
mqttclient.start_spin()

T = 20
F = 14
time.sleep(T)
mqttclient.stop_spin()

plt.plot(torques_time, torques)

plt.show()