import time
from src.pb_studio.core.system_monitor import SystemMonitor
from src.pb_studio.core.vram_arbiter import VRAMArbiter
from src.pb_studio.utils.logging_setup import setup_logging

setup_logging("test_hal")

print("--- Testing Hardware Abstraction Layer ---")
print("Initializing Monitor (This may take 1-2 sec to load DLL)...")

try:
    monitor = SystemMonitor()
    arbiter = VRAMArbiter(monitor)
    
    print("\nReading Stats (5 snapshots):")
    for i in range(5):
        stats = monitor.get_stats()
        print(f"[{i+1}/5] GPU Load: {stats['gpu_load']}% | Temp: {stats['gpu_temp']}°C | VRAM: {stats['gpu_memory_used']:.1f} MB Used")
        time.sleep(1)

    print("\nTesting Allocation Request:")
    allowed = arbiter.can_allocate(1000) # Request 1GB
    print(f"Request 1000MB: {'GRANTED' if allowed else 'DENIED'}")

    monitor.close()
    print("\n[OK] HAL Test Complete.")
except Exception as e:
    print(f"\n[FAIL] Test crashed: {e}")
