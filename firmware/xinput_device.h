#ifndef PEDAL_XINPUT_DEVICE_H
#define PEDAL_XINPUT_DEVICE_H
#include <stdbool.h>
#include <stdint.h>
bool xinput_device_ready(void);
bool xinput_device_send(const uint8_t report[20]);
void xinput_device_task(void);
void xinput_device_set_serial(uint32_t serial);
/* Application hooks, called in TinyUSB task context. */
void xinput_device_report_complete(bool success);
void xinput_device_get_report(uint8_t report[20]);
/* Validated standard wired rumble (00 08 00 left right 00 00 00). */
void xinput_device_output_report(const uint8_t report[8]);
#endif
