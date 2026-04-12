from pynput.keyboard import Key, Controller
import time

keyboard = Controller()

while True:
    keyboard.press(Key.down)
    keyboard.release(Key.down)
    keyboard.press(Key.enter)
    keyboard.release(Key.enter)
    time.sleep(60)