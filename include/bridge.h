#ifndef PEDAL_BRIDGE_H
#define PEDAL_BRIDGE_H
#include "pedal.h"
#include "xinput_pad.h"
#include <stdbool.h>
#include <stdint.h>

#define BRIDGE_HOST_TIMEOUT_MS 250u
#define BRIDGE_STICK_TOLERANCE 4000u
#define BRIDGE_NEUTRAL_STREAK_REQUIRED 2u

typedef enum {
    BRIDGE_HOST_ABSENT = 0,
    BRIDGE_HOST_ENUMERATING,
    BRIDGE_HOST_HANDSHAKING,
    BRIDGE_HOST_STREAMING,
    BRIDGE_HOST_STALE
} bridge_host_state_t;

typedef enum {
    BRIDGE_MERGE_OVERRIDE = 0,
    BRIDGE_MERGE_MAX
} bridge_merge_mode_t;

typedef struct {
    uint32_t timeout_ms;
    uint16_t stick_tolerance;
    bridge_merge_mode_t merge_mode;
    bool full_neutral_on_fault;
} bridge_config_t;

typedef struct {
    bridge_config_t config;
    bridge_host_state_t state;
    xinput_pad_t pad;
    uint16_t vid, pid;
    uint32_t mounted_ms;
    uint32_t last_report_ms;
    uint32_t valid_reports;
    uint32_t ignored_reports;
    uint32_t timeouts;
    uint8_t neutral_streak;
    bool host_seen;
    bool pad_valid;
} bridge_t;

void bridge_defaults(bridge_config_t *config);
void bridge_init(bridge_t *bridge, const bridge_config_t *config, uint32_t now_ms);
void bridge_host_mounted(bridge_t *bridge, uint16_t vid, uint16_t pid, uint32_t now_ms);
void bridge_host_handshake_done(bridge_t *bridge, uint32_t now_ms);
void bridge_host_report(bridge_t *bridge, const xinput_pad_t *pad, uint32_t now_ms);
void bridge_host_unmounted(bridge_t *bridge, uint32_t now_ms);
void bridge_tick(bridge_t *bridge, uint32_t now_ms);
bool bridge_host_ready(const bridge_t *bridge);
bool bridge_host_seen(const bridge_t *bridge);
bool bridge_requires_full_neutral(const bridge_t *bridge);
void bridge_build_report(const bridge_t *bridge, const pedal_t *pedal, bool blocked,
                         uint8_t report[XINPUT_PAD_REPORT_SIZE]);
#endif
