#ifndef PEDAL_HAL_H
#define PEDAL_HAL_H
#include <stdbool.h>
#include <stdint.h>
#define PEDAL_THROTTLE_GPIO 26
#define PEDAL_BRAKE_GPIO 27
#define PEDAL_MODE_GPIO 14
void pedal_hal_init(void);
void pedal_hal_read(uint16_t raw[2]);
bool pedal_hal_button(void);
#endif
