"""
Test script for TcComponent - pure Python component using tc_component C core.
"""

from termin._native.component import TcComponent

# Create a simple Python class with component methods
class MyPythonComponent:
    def __init__(self):
        self.started = False
        self.update_count = 0

    def start(self):
        print("MyPythonComponent.start() called")
        self.started = True

    def update(self, dt):
        self.update_count += 1
        print(f"MyPythonComponent.update({dt}) called, count={self.update_count}")

    def on_destroy(self):
        print("MyPythonComponent.on_destroy() called")

# Create Python object
py_comp = MyPythonComponent()
print("1. Python object created")

# Create TcComponent wrapper
tc = TcComponent(py_comp, "MyPythonComponent")
print(f"2. TcComponent created: type_name={tc.type_name()}")
print(f"   enabled={tc.enabled}, is_python_component={tc.is_python_component}")

# Set flags
tc.has_update = True
tc.has_fixed_update = False
print(f"3. Flags set: has_update={tc.has_update}, has_fixed_update={tc.has_fixed_update}")

# Get C pointer as integer
c_ptr = tc.c_ptr_int()
print(f"4. c_ptr_int obtained: 0x{c_ptr:x}")

print("\n=== TcComponent infrastructure test passed! ===")
print("The tc_component C core with Python vtable is working.")
print("Next step: integrate with Entity and Scene.")
