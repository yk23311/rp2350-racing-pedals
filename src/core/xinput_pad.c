#include "xinput_pad.h"
#include <string.h>

static uint16_t read_u16(const uint8_t *data) {
    return (uint16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
}
static int16_t read_i16(const uint8_t *data) {
    return (int16_t)read_u16(data);
}
static bool within(int16_t value, uint16_t tolerance) {
    int32_t magnitude = value;
    if (magnitude < 0) magnitude = -magnitude;
    return magnitude <= (int32_t)tolerance;
}

bool xinput_pad_parse_wired(const uint8_t *data, uint16_t len, xinput_pad_t *out) {
    if (data == NULL || out == NULL || len < XINPUT_PAD_REPORT_SIZE) return false;
    if (data[0] != 0x00 || data[1] != 0x14) return false;
    out->buttons = read_u16(data + 2);
    out->lt = data[4];
    out->rt = data[5];
    out->lx = read_i16(data + 6);
    out->ly = read_i16(data + 8);
    out->rx = read_i16(data + 10);
    out->ry = read_i16(data + 12);
    return true;
}

void xinput_pad_clear(xinput_pad_t *pad) {
    if (pad != NULL) memset(pad, 0, sizeof(*pad));
}

bool xinput_pad_is_neutral(const xinput_pad_t *pad, uint16_t stick_tolerance) {
    if (pad == NULL) return false;
    return pad->buttons == 0 && pad->lt == 0 && pad->rt == 0 &&
           within(pad->lx, stick_tolerance) && within(pad->ly, stick_tolerance) &&
           within(pad->rx, stick_tolerance) && within(pad->ry, stick_tolerance);
}

bool xinput_pad_buttons_triggers_neutral(const xinput_pad_t *pad) {
    if (pad == NULL) return false;
    return pad->buttons == 0 && pad->lt == 0 && pad->rt == 0;
}
