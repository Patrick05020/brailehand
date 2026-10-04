from gpiozero import OutputDevice
from time import sleep

for pin in[26, 19, 13]:
    m = OutputDevice(pin)
    m.on()
    sleep(1)
    m.off()
