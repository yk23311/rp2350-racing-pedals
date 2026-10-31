#ifndef PEDAL_USB_H
#define PEDAL_USB_H
#include "pedal.h"
#include "console.h"
void pedal_usb_init(pedal_t *pedal);
void pedal_usb_task(void);
bool pedal_usb_quiet(void);
bool pedal_usb_console(const char *line,char response[CONSOLE_RESPONSE_SIZE]);
bool pedal_usb_feed(console_input_t *input,char ch,pedal_t *pedal,console_save_fn save,void *context,char response[CONSOLE_RESPONSE_SIZE]);
#endif
