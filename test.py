from termin.core.profiler import Profiler
import time

p = Profiler.instance()
p.enabled = True

for i in range(5):
    p.begin_frame()
    with p.section("Test"):
        time.sleep(0.01)
        with p.section("Inner"):
            time.sleep(0.005)
    p.end_frame()

p.print_report()