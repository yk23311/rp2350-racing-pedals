#ifndef PEDAL_USB_H
#define PEDAL_USB_H
#include "pedal.h"
void pedal_usb_init(pedal_t *pedal);
void pedal_usb_task(void);
bool pedal_usb_quiet(void);
#endif
