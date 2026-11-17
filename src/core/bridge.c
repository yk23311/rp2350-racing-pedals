#include "bridge.h"
#include "xinput_protocol.h"
#include "control_profile.h"
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

static uint16_t merge_pedal(const pedal_t *pedal, unsigned axis, uint8_t trigger, bool merge_max) {
    uint16_t host_value=(uint16_t)(trigger*257u);
    if(!pedal->config.axis[axis].calibrated) return host_value;
    uint16_t value=pedal->output[axis];
    return merge_max && host_value>value ? host_value : value;
}

static void build_controls(const bridge_t *bridge, const pedal_t *pedal, bool blocked,
                           bool wheel, xinput_pad_t *pad, uint16_t *throttle, uint16_t *brake) {
    *pad=(xinput_pad_t){0};
    *throttle=*brake=0;
    if(blocked || pedal==NULL || !pedal->armed || !pedal->sample_valid ||
       pedal->calibration_axis>=0 || pedal->mode!=PEDAL_JOYSTICK ||
       bridge_requires_full_neutral(bridge)) return;

    const control_profile_t *profile=control_current();
    if(bridge_host_ready(bridge)) {
        uint8_t keyboard[8];
        control_transform(profile,&bridge->pad,pad,keyboard);
    }
    bool merge_max=wheel || (bridge && bridge->config.merge_mode==BRIDGE_MERGE_MAX);
    *throttle=merge_pedal(pedal,profile->throttle_axis,pad->rt,merge_max);
    *brake=merge_pedal(pedal,1u-profile->throttle_axis,pad->lt,merge_max);
}

void bridge_build_report(const bridge_t *bridge, const pedal_t *pedal, bool blocked,
                         uint8_t report[XINPUT_PAD_REPORT_SIZE]) {
    if(report==NULL) return;
    memset(report,0,XINPUT_PAD_REPORT_SIZE);
    report[1]=XINPUT_PAD_REPORT_SIZE;
    xinput_pad_t pad;
    uint16_t throttle,brake;
    build_controls(bridge,pedal,blocked,false,&pad,&throttle,&brake);
    put_u16(report+2,pad.buttons);
    report[4]=xinput_axis_quantize(brake);
    report[5]=xinput_axis_quantize(throttle);
    put_i16(report+6,pad.lx);
    put_i16(report+8,pad.ly);
    put_i16(report+10,pad.rx);
    put_i16(report+12,pad.ry);
}

void bridge_build_wheel_report(const bridge_t *bridge, const pedal_t *pedal, bool blocked,
                               uint8_t report[WHEEL_REPORT_SIZE]) {
    if(report==NULL) return;
    xinput_pad_t pad;
    uint16_t throttle,brake;
    build_controls(bridge,pedal,blocked,true,&pad,&throttle,&brake);
    /* XInput reserves two bits between RB and A. HID Button 1..14 is packed. */
    uint16_t buttons=(uint16_t)((pad.buttons&0x03ffu)|((pad.buttons&0xf000u)>>2));
    put_i16(report,pad.lx);
    put_u16(report+2,throttle);
    put_u16(report+4,brake);
    put_u16(report+6,buttons);
}
