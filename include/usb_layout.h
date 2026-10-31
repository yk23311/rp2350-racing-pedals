#ifndef USB_LAYOUT_H
#define USB_LAYOUT_H
#include <stddef.h>
#include <stdint.h>
extern const uint8_t usb_device_descriptor[18];
extern const uint8_t usb_configuration_descriptor[125];
extern const uint8_t usb_joystick_descriptor[];
extern const uint8_t usb_keyboard_descriptor[];
extern const size_t usb_joystick_descriptor_size,usb_keyboard_descriptor_size;
#endif
