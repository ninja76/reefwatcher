#!/usr/bin/python

import io
import sys
import fcntl
import time
import copy
import string
from AtlasI2C import (
	 AtlasI2C
)

device = AtlasI2C()
device_address_list = device.list_i2c_devices()

def get_ph():
    device.set_i2c_address(98)
    response = device.query("R")
    print("Response: " + response)
    
def main():
    get_ph()
    
if __name__ == '__main__':
    main()
