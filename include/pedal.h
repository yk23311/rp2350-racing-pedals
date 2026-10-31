#ifndef PEDAL_H
#define PEDAL_H
#include <stdbool.h>
#include <stdint.h>
#define PEDAL_AXES 2
#define PEDAL_WINDOW_MAX 8
#define PEDAL_ADC_MAX 4095
#define PEDAL_MIN_SPAN 128

typedef struct {
    uint16_t released, pressed;
    uint16_t on, off; /* fraction of travel in 1/10000 */
    uint16_t gamma;   /* exponent in 1/100 */
    uint8_t window;
    bool calibrated;
} pedal_axis_config_t;
typedef struct { pedal_axis_config_t axis[PEDAL_AXES]; } pedal_config_t;
typedef enum { PEDAL_JOYSTICK, PEDAL_KEYBOARD } pedal_mode_t;
typedef struct {
    uint16_t samples[PEDAL_WINDOW_MAX];
    uint32_t sum;
    uint8_t count, next;
    bool active;
} pedal_filter_t;
typedef struct {
    pedal_config_t config;
    pedal_filter_t filter[PEDAL_AXES];
    uint16_t raw[PEDAL_AXES], filtered[PEDAL_AXES], output[PEDAL_AXES];
    pedal_mode_t mode;
    bool armed, sample_valid;
    int calibration_axis; /* -1 means idle */
    uint16_t cal_released, cal_min, cal_max;
    uint32_t generation;
} pedal_t;
typedef struct {
    bool candidate, stable, fired;
    uint32_t changed_ms, pressed_ms;
} pedal_button_t;

void pedal_defaults(pedal_config_t *config);
bool pedal_config_valid(const pedal_config_t *config);
void pedal_init(pedal_t *pedal, const pedal_config_t *config);
bool pedal_apply(pedal_t *pedal, const pedal_config_t *config);
void pedal_reset(pedal_t *pedal);
void pedal_sample(pedal_t *pedal, const uint16_t raw[PEDAL_AXES]);
bool pedal_cal_begin(pedal_t *pedal, unsigned axis);
bool pedal_cal_end(pedal_t *pedal);
void pedal_cal_cancel(pedal_t *pedal);
void pedal_mode(pedal_t *pedal, pedal_mode_t mode);
void pedal_keyboard(const pedal_t *pedal, uint8_t report[8]);
bool pedal_button_update(pedal_button_t *button, bool down, uint32_t now_ms);
#endif
