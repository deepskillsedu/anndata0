from app.ditto_reader import get_twin

print(get_twin())


from app.ditto_reader import (
    get_actual,
    get_virtual,
    get_attributes
)

print("ATTRIBUTES")
print(get_attributes())

print("\nACTUAL")
print(get_actual())

print("\nVIRTUAL")
print(get_virtual())



