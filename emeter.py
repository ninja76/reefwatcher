import os
import time
import asyncio

from kasa import SmartStrip
from prometheus_client import start_http_server, Summary, Gauge, Counter, push_to_gateway, CollectorRegistry
from prometheus_client.exposition import basic_auth_handler, tls_auth_handler

heater_running_gauge = Gauge('heater_running', 'Heater Running')
heater_power_gauge = Gauge('heater_power', 'Heater Power Usage')
return_power_gauge = Gauge('return_power', 'Return Pump Power Usage')
ato_power_gauge = Gauge('ato_power', 'ATO Pump Power Usage')
led_power_gauge = Gauge('led_power', 'LED Power Usage')
wave_power_gauge = Gauge('wave_power', 'Wave Maker Power Usage')
pi_power_gauge = Gauge('pi_power', 'RPI Power Usage')
total_power_gauge = Gauge('total_power', 'Total Power Usage')

def main():
    dev = SmartStrip("192.168.0.42")  # We create the instance inside the main loop
    asyncio.run(dev.update())
#    print(asyncio.run(dev.current_consumption()))
    for plug in dev.children:
        if plug.alias == "Heater":
            heater_power_gauge.set(plug.emeter_realtime['power'])
            if plug.emeter_realtime['power'] > 0:
                heater_running_gauge.set(1)
            else:
                heater_running_gauge.set(0)
        elif plug.alias == "Return pump":
            return_power_gauge.set(plug.emeter_realtime['power'])
        elif plug.alias == "ATO pump":
            ato_power_gauge.set(plug.emeter_realtime['power'])
        elif plug.alias == "Wavemaker":
            wave_power_gauge.set(plug.emeter_realtime['power'])
        elif plug.alias == "Reefwatcher":
            pi_power_gauge.set(plug.emeter_realtime['power'])
        elif plug.alias == "Led":
            led_power_gauge.set(plug.emeter_realtime['power'])
        print(f"{plug.alias} {plug.emeter_realtime['power']}")

#    os.system("kasa --host 192.168.0.42 emeter --erase")
    print(f"{dev.emeter_realtime['total']}")
    total_power_gauge.set(dev.emeter_realtime['total']) 
    #asyncio.run(dev.erase_emeter_stats())

if __name__ == "__main__":
    start_http_server(8001)
    while True:
        print("derp")
        try:
            main()
        except:
            print("error")
        time.sleep(10)
