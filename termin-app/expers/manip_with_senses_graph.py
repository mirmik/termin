#!/usr/bin/env python3

import rxsignal
import rxsignal.rxmqtt
import time
import rxsignal.flowchart
import matplotlib.pyplot as plt
import pickle

#chart = rxsignal.flowchart.FlowChart()

collect_coords = []
collect_coords_time = []
collect_data = []
collect_time = []
barrier_data = []
barrier_time = []
accels_data = []
accels_time = []
vels_data = []
vels_time = []
posout_data = []
posout_time = []

start_time = time.time()
last_draw = 0

mqttclient = rxsignal.rxmqtt.mqtt_rxclient()

def coords(data):
    collect_coords.append(data)
    collect_coords_time.append(time.time() - start_time)

def pos(data):
    posout_data.append(data)
    posout_time.append(time.time() - start_time)

def worker(data):
    curtime = time.time() - start_time
    collect_data.append(data)
    collect_time.append(curtime)

def barrier_worker(data):
    barrier_data.append(data)
    barrier_time.append(time.time() - start_time)
   
def accels_worker(data):
    accels_data.append(data)
    accels_time.append(time.time() - start_time)
    
def vels_worker(data):
    vels_data.append(data)
    vels_time.append(time.time() - start_time)
     
mqttclient.subscribe("pos_error_norm", worker)
mqttclient.subscribe("posout", pos)
mqttclient.subscribe("coords", coords)
mqttclient.subscribe("barrier", barrier_worker)
mqttclient.subscribe("accels", accels_worker)
mqttclient.subscribe("vels", vels_worker)
mqttclient.start_spin()

T = 20
F = 14
time.sleep(T)
mqttclient.stop_spin()

# plot two subplots
fig, ((ax5, ax4), (ax6, ax1), (ax2, ax3)) = plt.subplots(3, 2)

ax1.plot(collect_time, collect_data, 'k')
#ax1.set_xlabel('время, с', fontsize=F)
ax1.set_ylabel('невязка, см', fontsize=F)

ax2.plot(collect_coords_time, collect_coords, 'k')
ax2.set_xlabel('время, с', fontsize=F)
ax2.set_ylabel('координаты, рад', fontsize=F)

ax4.plot(posout_time, posout_data, 'k')
#ax4.set_xlabel('время, с', fontsize=F)
ax4.set_ylabel('положение ВЗ, см', fontsize=F)

# set line width
ax3.plot(barrier_time, barrier_data, 'k', linewidth=1)
ax3.set_xlabel('время, с', fontsize=F)
ax3.set_ylabel('барьерный потенциал, ед', fontsize=F)

ax5.plot(accels_time, accels_data, 'k', linewidth=1)
#ax5.set_xlabel('время, с', fontsize=F)
ax5.set_ylabel('ускорения, см/c2', fontsize=F)

ax6.plot(vels_time, vels_data, 'k', linewidth=1)
#ax6.set_xlabel('время, с', fontsize=F)
ax6.set_ylabel('скорости, см/c', fontsize=F)

plt.show()