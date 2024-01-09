import os
import glob
import board
import busio
import time
import smbus2
import digitalio
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
from prometheus_client import start_http_server, Summary, Gauge
from prometheus_client.exposition import basic_auth_handler, tls_auth_handler
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_bmp280
import adafruit_tsl2591
from fonts.ttf import RobotoLight as UserFont

#Water level sensor setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN)

ato_pin = 11
#ATO float switch
GPIO.setup(ato_pin, GPIO.IN)

# Initialize the I2C interface(s)
#i2c-4 for ads1115 adc
i2c4 = I2C(4)
ads = ADS.ADS1115(i2c4)
channel0 = AnalogIn(ads, ADS.P0)
# Main i2c
i2c1 = busio.I2C(board.SCL, board.SDA)
#mcp = adafruit_mcp9808.MCP9808(i2c1)
bme280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c1)
lux_sensor = adafruit_tsl2591.TSL2591(i2c1)

# OLED Stuff
WIDTH = 128
HEIGHT = 64  # Change to 64 if needed
BORDER = 5
from luma.core.interface.serial import i2c
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import sh1106
serial = i2c(port=1, address=0x3C)
oled = sh1106(serial)

font_size = 18 
font = ImageFont.truetype(UserFont, font_size)

# Prometheus config
registry = CollectorRegistry()

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
 
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

temp_probes = ["/sys/bus/w1/devices/28-3ce1d4433a17/w1_slave",
               "/sys/bus/w1/devices/28-3ce1d443ede3/w1_slave"]

#i2c config
# BME280 sensor address (default address)
bme280_address = 0x76
# TDS sensor address
tds_address = 0x40

# Load calibration parameters
try:
    calibration_params = bme280.load_calibration_params(bus, bme280_address)
except:
    print("prod with bme280")

temp_history = []

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
        if len(temp_history) > 160:    
            print("popping")
            temp_history.pop(0)
        temp_history.append(temp_f)
    return results        

def read_ambient_temp():
    # Print the readings
    print("Ambient Temperature: {:.0f} °F".format(celsius_to_fahrenheit(bme280.temperature)))
    print("Pressure: {:.2f} hPa".format(bme280.pressure))

    amb_temp_gauge.set(celsius_to_fahrenheit(bme280.temperature))
    #humidity_gauge.set(bme280.humidity)
    return celsius_to_fahrenheit(bme280.temperature)

def read_tds():
    voltage = channel0.voltage 
    tds_value = (133.42/voltage*voltage*voltage-255.86*voltage*voltage+857.39*voltage)*0.5
    print("Water quality: {:.2f} ppm".format(tds_value))
    tds_gauge.set(tds_value)
    return tds_value

def read_mcp9808():
    print('Ambient Temperature: {} degrees C'.format(celsius_to_fahrenheit(mcp.temperature))) 
    amb_temp_gauge.set(celsius_to_fahrenheit(mcp.temperature))
    return celsius_to_fahrenheit(mcp.temperature)

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

def draw_graph(variable, probe_1, probe_2, amb, ppm):
    header = "Temp 1/2"
    message = "{:.0f}°F/{:.0f}°F".format(probe_1, probe_2)
    message1 = "Quality {:.1f}ppm".format(ppm)
    HEIGHT = 64
    WIDTH = 128
    shape = []
#    data = data[-160:]
    with canvas(oled) as draw:
        draw.text((10, 10), header, font=font, fill="white")
        draw.text((10, 26), message, font=font, fill="white")
        draw.text((10, 42), message1, font=font, fill="white")

def my_auth_handler(url, method, timeout, headers, data):
    username = '1355835'
    password = 'glc_eyJvIjoiMzc5MDI4IiwibiI6InN0YWNrLTgyMzI3OS1obS13cml0ZS1yZWVmIiwiayI6Ilg5N1FseE1rTzA4ODJ1U2I4QWNwOEE0NiIsIm0iOnsiciI6InByb2QtdXMtZWFzdC0wIn19'
    return basic_auth_handler(url, method, timeout, headers, data, username, password)

def read_sensors():
    (probe_1, probe_2) = read_water_temp()
    ambient_temp = read_ambient_temp()
    ppm = read_tds()
    water_level = check_water_level()
    lux = read_tsl2591()
    draw_graph("Temp", probe_1, probe_2, ambient_temp, ppm)   

if __name__ == '__main__':
    start_http_server(8000)
    image = Image.new("1", (oled.width, oled.height))
    font = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf', 12)
    font_small = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf', 10)

    while True:
        try:
            read_sensors()
        except:
            print("Problem with read_sensors")
        time.sleep(5)
