import os
import glob
import board
import busio
import time
import smbus2
import digitalio
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
from prometheus_client import start_http_server, Gauge
#from prometheus_client.exposition import basic_auth_handler, tls_auth_handler
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_bme280 import basic as adafruit_bme280
import adafruit_tsl2591
from fonts.ttf import RobotoLight as UserFont
import asyncio
from kasa import SmartStrip
from AtlasI2C import (
         AtlasI2C
)

#PH probe config
device = AtlasI2C()
device_address_list = device.list_i2c_devices()

#Water level sensor setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN)

ato_pin = 21 
#ATO float switch
GPIO.setup(ato_pin, GPIO.IN)

# Initialize the I2C interface(s)
i2c1 = busio.I2C(board.SCL, board.SDA)
#ads = ADS.ADS1115(i2c1)
#channel0 = AnalogIn(ads, ADS.P0)
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c1, address=0x76)
bme280.sea_level_pressure = 1013.25

#$lux_sensor = adafruit_tsl2591.TSL2591(i2c1)

# OLED Stuff
WIDTH = 128
HEIGHT = 32  # Change to 64 if needed
BORDER = 5
from luma.core.interface.serial import i2c
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import sh1106
#serial = i2c(port=1, address=0x3C)
#oled = sh1106(serial)

font_size = 24 
font = ImageFont.truetype(UserFont, font_size)

# Prometheus config
amb_temp_gauge = Gauge('ambient_temp', 'Ambient Temperature')#, registry=registry)
humidity_gauge = Gauge('humidity_temp', 'Humidity')#, registry=registry)
lux_gauge = Gauge('lux', 'Light')#, registry=registry)
ir_gauge = Gauge('ir', 'IR')#, registry=registry)
visible_gauge = Gauge('visible', 'Visible')#, registry=registry)
water_temp_gauge = Gauge('water_1_temp', 'Water Temperature 1')#, registry=registry)
water2_temp_gauge = Gauge('water_2_temp', 'Water Temperature 2')#, registry=registry)
tds_gauge = Gauge('water_tds', 'TDS ppm')#, registry=registry)
water_level_gauge = Gauge('water_level', 'Water level')#, registry=registry)
ato_water_level_gauge = Gauge('ato_water_level', 'ATO Water level')#, registry=registry)
ph_gauge = Gauge('ph_level', 'PH Level')
heater_running_gauge = Gauge('heater_running', 'Heater Running')
heater_power_gauge = Gauge('heater_power', 'Heater Power Usage')
return_power_gauge = Gauge('return_power', 'Return Pump Power Usage')
ato_power_gauge = Gauge('ato_power', 'ATO Pump Power Usage')
led_power_gauge = Gauge('led_power', 'LED Power Usage')
wave_power_gauge = Gauge('wave_power', 'Wave Maker Power Usage')
pi_power_gauge = Gauge('pi_power', 'RPI Power Usage')
total_power_gauge = Gauge('total_power', 'Total Power Usage')

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

temp_probes = ["/sys/bus/w1/devices/28-3ce1d4433a17/w1_slave",
               "/sys/bus/w1/devices/28-00000014f1fd/w1_slave"]

#temp_probes = ["/sys/bus/w1/devices/28-20000014f1fd/w1_slave"]

#i2c config
bme280_address = 0x76
tds_address = 0x40

def get_ph():
    device.set_i2c_address(98)
    response = device.query("R")
    v =	response.split(':')[1].split('  ')[0].split('\x00')[0]
    print(float(v))
    ph_gauge.set(float(v))
    return float(v)

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32
 
def read_water_temp_raw(probe_file):
    f = open(probe_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_water_temp():
    results = []
    for p in range(len(temp_probes)):
        lines = read_water_temp_raw(temp_probes[p])
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = read_water_temp_raw(temp_probes[p])
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string) / 1000.0
            temp_f = celsius_to_fahrenheit(temp_c)# * 9.0 / 5.0 + 32.0
            print("Water Temperature {}: {:.0f} °F".format(p, temp_f))
            results.append(temp_f)
            if p == 0:
                water_temp_gauge.set(temp_f)
            else:
                water2_temp_gauge.set(temp_f)
    return results

def read_ambient_temp():
    # Print the readings
    print("Ambient Temperature: {:.0f} °F".format(celsius_to_fahrenheit(bme280.temperature)))
    print("Pressure: {:.2f} hPa".format(bme280.pressure))
    print("Humidity: {:.2f} %".format(bme280.relative_humidity))

    humidity_gauge.set(bme280.relative_humidity)
    amb_temp_gauge.set(celsius_to_fahrenheit(bme280.temperature))
    #humidity_gauge.set(bme280.humidity)
    return celsius_to_fahrenheit(bme280.temperature)

def check_water_level():
    is_okay = GPIO.input(21)
    ato_is_okay = GPIO.input(ato_pin)
    water_level_gauge.set(is_okay)
    ato_water_level_gauge.set(ato_is_okay)
    print("Water Level: {}".format(is_okay)) 
    print("ATO Water Level: {}".format(ato_is_okay)) 
    return is_okay

def read_tsl2591():
    print('Light: {:.0f}lux'.format(lux_sensor.lux))
    print('Visible: {0}'.format(lux_sensor.visible))
    print('Infrared: {0}'.format(lux_sensor.infrared))
    lux_gauge.set("{:.0f}".format(lux_sensor.lux))
    ir_gauge.set("{:.0f}".format(lux_sensor.infrared))
    visible_gauge.set("{:.0f}".format(lux_sensor.visible))
    return lux_sensor.lux

def update_display(probe_1, probe_2, ph, power):
    line  = "Tank:  {:.0f}°F/{:.0f}°F".format(probe_1, probe_2)
    line1 = "PH:    {:.1f}".format(ph)
    line2 = "Power: {:.1f}kwh".format(power)
    line3 = "ATO:   {}".format("OK")

#    with canvas(oled) as draw:
#        draw.text((1, 1), line, font=font, fill="white")
#        draw.text((1, 16), line1, font=font, fill="white")
#        draw.text((1, 31), line2, font=font, fill="white")

def read_sensors():
    try:
        temp_results = read_water_temp()
    except:
        print("404")
    ambient_temp = read_ambient_temp()
    ph = get_ph()
    water_level = check_water_level()
#    lux = read_tsl2591()
    try:
        power = read_power()
    except:
        power = -1
    print(ph)
    print(power)
    #update_display(temp_results[0], temp_results[1], ph, power)   

def read_power():
    dev = SmartStrip("192.168.0.42")  # We create the instance inside the main loop
    asyncio.run(dev.update())
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

    print(f"{dev.emeter_realtime['total']}")
    total_power_gauge.set(dev.emeter_realtime['total']) 
    return plug.emeter_realtime['power']

if __name__ == '__main__':
    start_http_server(8000)
#    image = Image.new("1", (oled.width, oled.height))
#    font = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf', 12)
#    font_small = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf', 10)

    while True:
        try:
            read_sensors()
        except:
            print("Problem with read_sensors")
        time.sleep(30)
