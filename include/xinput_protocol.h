#ifndef PEDAL_XINPUT_PROTOCOL_H
#define PEDAL_XINPUT_PROTOCOL_H
#include "pedal.h"
#include <stddef.h>
#define XINPUT_REPORT_SIZE 20
#define XINPUT_CONFIG_SIZE 140
extern const uint8_t xinput_device_descriptor[18];
extern const uint8_t xinput_configuration_descriptor[XINPUT_CONFIG_SIZE];
extern const uint16_t xinput_os_string[9];
extern const uint8_t xinput_compatible_id[40];
void xinput_report_build(const pedal_t *pedal,bool neutral,uint8_t report[XINPUT_REPORT_SIZE]);
/* Returns response length, or -1 to STALL an unsupported request. */
int xinput_control_response(uint8_t type,uint8_t request,uint16_t value,uint16_t index,uint8_t response[64]);
#endif
