"""
Script de test pour vérifier la disponibilité de la touche Windows dans pynput
"""
import platform
from pynput.keyboard import Key, Controller

print(f"Platform: {platform.system()}")
print(f"Platform version: {platform.version()}")
print("\nTesting Key attributes:")

# Liste des attributs de Key qui peuvent correspondre à la touche Windows
possible_keys = ['cmd', 'cmd_l', 'cmd_r', 'super', 'super_l', 'super_r']

for key_name in possible_keys:
    if hasattr(Key, key_name):
        key_obj = getattr(Key, key_name)
        print(f"✓ Key.{key_name} exists: {key_obj}")
    else:
        print(f"✗ Key.{key_name} does NOT exist")

print("\n" + "="*50)
print("Testing Windows key press (will open Start menu if working)...")
print("You have 3 seconds to cancel with Ctrl+C if needed")
print("="*50)

import time
time.sleep(3)

keyboard = Controller()

# Tester différentes méthodes
print("\nMethod 1: Using Key.cmd")
try:
    keyboard.press(Key.cmd)
    time.sleep(0.1)
    keyboard.release(Key.cmd)
    print("✓ Key.cmd press/release succeeded")
except Exception as e:
    print(f"✗ Key.cmd failed: {e}")

time.sleep(1)

# Fermer le menu démarrage si ouvert
try:
    keyboard.press(Key.esc)
    keyboard.release(Key.esc)
except:
    pass

print("\nTest completed!")
