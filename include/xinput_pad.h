#ifndef PEDAL_XINPUT_PAD_H
#define PEDAL_XINPUT_PAD_H
#include <stdbool.h>
#include <stdint.h>
#define XINPUT_PAD_REPORT_SIZE 20
typedef struct {
    uint16_t buttons;
    uint8_t lt, rt;
    int16_t lx, ly, rx, ry;
} xinput_pad_t;
/* Parse the standard wired Xbox 360 20-byte input report.
 * Accepts len >= 20 with report id 0x00 and size 0x14; leaves *out
 * unchanged on rejection. */
bool xinput_pad_parse_wired(const uint8_t *data, uint16_t len, xinput_pad_t *out);
void xinput_pad_clear(xinput_pad_t *pad);
/* Neutral means no buttons, no triggers and every stick within tolerance. */
bool xinput_pad_is_neutral(const xinput_pad_t *pad, uint16_t stick_tolerance);
/* Used for SAVE: sticks may drift, buttons/triggers may not be held. */
bool xinput_pad_buttons_triggers_neutral(const xinput_pad_t *pad);
#endif
