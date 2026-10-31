#include "bridge.h"
#include "xinput_protocol.h"
#include <string.h>

static void put_u16(uint8_t *data, uint16_t value) {
    data[0] = (uint8_t)(value & 0xFFu);
    data[1] = (uint8_t)(value >> 8);
}
static void put_i16(uint8_t *data, int16_t value) {
    put_u16(data, (uint16_t)value);
}

void bridge_defaults(bridge_config_t *config) {
    if (config == NULL) return;
    config->timeout_ms = BRIDGE_HOST_TIMEOUT_MS;
    config->stick_tolerance = BRIDGE_STICK_TOLERANCE;
    config->merge_mode = BRIDGE_MERGE_OVERRIDE;
    config->full_neutral_on_fault = true;
}

void bridge_init(bridge_t *bridge, const bridge_config_t *config, uint32_t now_ms) {
    if (bridge == NULL) return;
    memset(bridge, 0, sizeof(*bridge));
    bridge_defaults(&bridge->config);
    if (config != NULL) bridge->config = *config;
    if (bridge->config.timeout_ms == 0) bridge->config.timeout_ms = BRIDGE_HOST_TIMEOUT_MS;
    if (bridge->config.timeout_ms > 10000u) bridge->config.timeout_ms = 10000u;
    if (bridge->config.stick_tolerance > 32767u) bridge->config.stick_tolerance = 32767u;
    bridge->state = BRIDGE_HOST_ABSENT;
    bridge->mounted_ms = now_ms;
    bridge->last_report_ms = now_ms;
}

void bridge_host_mounted(bridge_t *bridge, uint16_t vid, uint16_t pid, uint32_t now_ms) {
    if (bridge == NULL) return;
    bridge->host_seen = true;
    bridge->state = BRIDGE_HOST_ENUMERATING;
    bridge->vid = vid;
    bridge->pid = pid;
    bridge->mounted_ms = now_ms;
    bridge->last_report_ms = now_ms;
    bridge->valid_reports = 0;
    bridge->ignored_reports = 0;
    bridge->neutral_streak = 0;
    bridge->pad_valid = false;
    xinput_pad_clear(&bridge->pad);
}

void bridge_host_handshake_done(bridge_t *bridge, uint32_t now_ms) {
    if (bridge == NULL) return;
    if (bridge->state == BRIDGE_HOST_ENUMERATING) {
        bridge->state = BRIDGE_HOST_HANDSHAKING;
        bridge->last_report_ms = now_ms;
    }
}

void bridge_host_report(bridge_t *bridge, const xinput_pad_t *pad, uint32_t now_ms) {
    if (bridge == NULL || pad == NULL) return;
    if (bridge->state == BRIDGE_HOST_ABSENT) {
        bridge->ignored_reports++;
        return;
    }
    if (bridge->state == BRIDGE_HOST_STALE) {
        bridge->state = BRIDGE_HOST_HANDSHAKING;
        bridge->pad_valid = false;
        bridge->neutral_streak = 0;
    } else if (bridge->state == BRIDGE_HOST_ENUMERATING) {
        bridge->state = BRIDGE_HOST_HANDSHAKING;
    }
    bridge->pad = *pad;
    bridge->pad_valid = true;
    bridge->last_report_ms = now_ms;
    bridge->valid_reports++;
    if (xinput_pad_is_neutral(pad, bridge->config.stick_tolerance)) {
        if (bridge->neutral_streak < 255u) bridge->neutral_streak++;
    } else {
        bridge->neutral_streak = 0;
    }
    if (bridge->neutral_streak >= BRIDGE_NEUTRAL_STREAK_REQUIRED &&
        bridge->valid_reports >= BRIDGE_NEUTRAL_STREAK_REQUIRED) {
        bridge->state = BRIDGE_HOST_STREAMING;
    }
}

void bridge_host_unmounted(bridge_t *bridge, uint32_t now_ms) {
    if (bridge == NULL) return;
    bridge->state = BRIDGE_HOST_ABSENT;
    bridge->pad_valid = false;
    bridge->neutral_streak = 0;
    bridge->last_report_ms = now_ms;
    xinput_pad_clear(&bridge->pad);
}

void bridge_tick(bridge_t *bridge, uint32_t now_ms) {
    if (bridge == NULL) return;
    if (bridge->state != BRIDGE_HOST_STREAMING && bridge->state != BRIDGE_HOST_HANDSHAKING) return;
    if ((uint32_t)(now_ms - bridge->last_report_ms) > bridge->config.timeout_ms) {
        bridge->state = BRIDGE_HOST_STALE;
        bridge->pad_valid = false;
        bridge->neutral_streak = 0;
        bridge->timeouts++;
        xinput_pad_clear(&bridge->pad);
    }
}

bool bridge_host_ready(const bridge_t *bridge) {
    return bridge != NULL && bridge->state == BRIDGE_HOST_STREAMING && bridge->pad_valid;
}

bool bridge_host_seen(const bridge_t *bridge) {
    return bridge != NULL && bridge->host_seen;
}

bool bridge_requires_full_neutral(const bridge_t *bridge) {
    if (bridge == NULL || !bridge->host_seen) return false;
    if (bridge->state == BRIDGE_HOST_STREAMING) return false;
    return bridge->config.full_neutral_on_fault;
}

void bridge_build_report(const bridge_t *bridge, const pedal_t *pedal, bool blocked,
                         uint8_t report[XINPUT_PAD_REPORT_SIZE]) {
    if (report == NULL) return;
    memset(report, 0, XINPUT_PAD_REPORT_SIZE);
    report[1] = XINPUT_PAD_REPORT_SIZE;
    if (blocked || pedal == NULL) return;
    if (!pedal->armed || !pedal->sample_valid || pedal->calibration_axis >= 0 ||
        pedal->mode != PEDAL_JOYSTICK) return;

    bool host_live = bridge != NULL && bridge->state == BRIDGE_HOST_STREAMING && bridge->pad_valid;
    if (!host_live && bridge_requires_full_neutral(bridge)) return;

    if (host_live) {
        put_u16(report + 2, bridge->pad.buttons);
        put_i16(report + 6, bridge->pad.lx);
        put_i16(report + 8, bridge->pad.ly);
        put_i16(report + 10, bridge->pad.rx);
        put_i16(report + 12, bridge->pad.ry);
    }

    bool throttle_owned = pedal->config.axis[0].calibrated;
    bool brake_owned = pedal->config.axis[1].calibrated;
    uint8_t rt = throttle_owned ? xinput_axis_quantize(pedal->output[0]) : 0;
    uint8_t lt = brake_owned ? xinput_axis_quantize(pedal->output[1]) : 0;
    if (host_live) {
        if (!throttle_owned) {
            rt = bridge->pad.rt;
        } else if (bridge->config.merge_mode == BRIDGE_MERGE_MAX && bridge->pad.rt > rt) {
            rt = bridge->pad.rt;
        }
        if (!brake_owned) {
            lt = bridge->pad.lt;
        } else if (bridge->config.merge_mode == BRIDGE_MERGE_MAX && bridge->pad.lt > lt) {
            lt = bridge->pad.lt;
        }
    }
    report[4] = lt;
    report[5] = rt;
}
