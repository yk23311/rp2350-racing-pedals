#include "bridge.h"
#include "xinput_protocol.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x);exit(1); } } while(0)

static pedal_t ready_pedal(void) {
    pedal_config_t config;
    pedal_defaults(&config);
    for (unsigned i = 0; i < PEDAL_AXES; i++) config.axis[i].calibrated = true;
    pedal_t pedal;
    pedal_init(&pedal, &config);
    pedal.armed = true;
    pedal.sample_valid = true;
    pedal.mode = PEDAL_JOYSTICK;
    pedal.calibration_axis = -1;
    return pedal;
}

static xinput_pad_t make_pad(uint16_t buttons, int16_t lx, uint8_t lt, uint8_t rt) {
    xinput_pad_t pad;
    memset(&pad, 0, sizeof(pad));
    pad.buttons = buttons;
    pad.lx = lx;
    pad.lt = lt;
    pad.rt = rt;
    return pad;
}

static void get_streaming(bridge_t *bridge, const bridge_config_t *config) {
    bridge_init(bridge, config, 0);
    bridge_host_mounted(bridge, 0x20BC, 0x5128, 0);
    bridge_host_handshake_done(bridge, 1);
    xinput_pad_t neutral = make_pad(0, 0, 0, 0);
    bridge_host_report(bridge, &neutral, 10);
    bridge_host_report(bridge, &neutral, 20);
    CHECK(bridge_host_ready(bridge));
}

static void expect_all_zero(const uint8_t report[20]) {
    CHECK(report[0] == 0 && report[1] == 20);
    for (unsigned i = 2; i < 20; i++) CHECK(report[i] == 0);
}

static void pedal_only(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_t bridge;
    bridge_init(&bridge, &config, 0);
    CHECK(!bridge_host_seen(&bridge));
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 65535;
    pedal.output[1] = 32768;
    uint8_t report[20];
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[0] == 0 && report[1] == 20);
    CHECK(report[4] == 128 && report[5] == 255);
    for (unsigned i = 2; i < 20; i++) if (i != 4 && i != 5) CHECK(report[i] == 0);

    bridge_build_report(NULL, &pedal, false, report);
    CHECK(report[4] == 128 && report[5] == 255);

    pedal.config.axis[0].calibrated = false;
    pedal.config.axis[1].calibrated = false;
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 0 && report[5] == 0);
}

static void handshake(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_t bridge;
    bridge_init(&bridge, &config, 0);
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 65535;
    pedal.output[1] = 65535;
    uint8_t report[20];

    bridge_host_mounted(&bridge, 0x20BC, 0x5128, 0);
    CHECK(bridge.state == BRIDGE_HOST_ENUMERATING);
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    bridge_host_handshake_done(&bridge, 1);
    CHECK(bridge.state == BRIDGE_HOST_HANDSHAKING);
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    xinput_pad_t active = make_pad(0x1000, 1000, 0, 0);
    bridge_host_report(&bridge, &active, 10);
    CHECK(!bridge_host_ready(&bridge));
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    xinput_pad_t neutral = make_pad(0, 0, 0, 0);
    bridge_host_report(&bridge, &neutral, 20);
    CHECK(!bridge_host_ready(&bridge));
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    bridge_host_report(&bridge, &neutral, 30);
    CHECK(bridge_host_ready(&bridge));
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 255 && report[5] == 255);
    CHECK(report[2] == 0 && report[3] == 0);

    bridge_host_report(&bridge, &active, 40);
    CHECK(bridge_host_ready(&bridge));
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 255 && report[5] == 255);
    CHECK(report[2] == 0 && report[3] == 0x10);
    CHECK((int16_t)(report[6] | (report[7] << 8)) == 1000);

    CHECK(xinput_pad_buttons_triggers_neutral(&neutral));
}

static void override(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_t bridge;
    get_streaming(&bridge, &config);
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 0;
    pedal.output[1] = 0;
    xinput_pad_t pad = make_pad(0, 0, 200, 200);
    bridge_host_report(&bridge, &pad, 30);
    uint8_t report[20];
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 0 && report[5] == 0);

    pedal.output[0] = 65535;
    pedal.output[1] = 65535;
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 255 && report[5] == 255);

    pedal.config.axis[0].calibrated = false;
    pedal.output[0] = 0;
    bridge_host_report(&bridge, &pad, 40);
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[5] == 200 && report[4] == 255);

    pedal.config.axis[0].calibrated = true;
    pedal.config.axis[1].calibrated = false;
    pedal.output[0] = 65535;
    pedal.output[1] = 0;
    bridge_host_report(&bridge, &pad, 50);
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 200 && report[5] == 255);
}

static void max_merge(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    config.merge_mode = BRIDGE_MERGE_MAX;
    bridge_t bridge;
    get_streaming(&bridge, &config);
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 0;
    pedal.output[1] = 0;
    xinput_pad_t pad = make_pad(0, 0, 100, 200);
    bridge_host_report(&bridge, &pad, 30);
    uint8_t report[20];
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 100 && report[5] == 200);

    pedal.output[0] = 65535;
    pedal.output[1] = 32768;
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[4] == 128 && report[5] == 255);
}

static void timeout(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_t bridge;
    get_streaming(&bridge, &config);
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 65535;
    uint8_t report[20];

    bridge_tick(&bridge, 270);
    CHECK(bridge.state == BRIDGE_HOST_STREAMING);
    bridge_tick(&bridge, 271);
    CHECK(bridge.state == BRIDGE_HOST_STALE);
    CHECK(bridge.timeouts == 1);
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    xinput_pad_t neutral = make_pad(0, 0, 0, 0);
    bridge_host_report(&bridge, &neutral, 280);
    CHECK(bridge.state == BRIDGE_HOST_HANDSHAKING);
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);
    bridge_host_report(&bridge, &neutral, 290);
    CHECK(bridge_host_ready(&bridge));
    bridge_build_report(&bridge, &pedal, false, report);
    CHECK(report[5] == 255);
}

static void unmount(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_t bridge;
    get_streaming(&bridge, &config);
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 65535;
    uint8_t report[20];
    bridge_host_unmounted(&bridge, 100);
    CHECK(bridge.state == BRIDGE_HOST_ABSENT);
    CHECK(bridge_host_seen(&bridge));
    CHECK(bridge_requires_full_neutral(&bridge));
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    bridge_host_mounted(&bridge, 0x20BC, 0x5128, 110);
    bridge_host_handshake_done(&bridge, 111);
    xinput_pad_t neutral = make_pad(0, 0, 0, 0);
    bridge_host_report(&bridge, &neutral, 120);
    bridge_host_report(&bridge, &neutral, 130);
    CHECK(bridge_host_ready(&bridge));

    bridge_config_t pedal_only_config;
    bridge_defaults(&pedal_only_config);
    pedal_only_config.full_neutral_on_fault = false;
    bridge_t pedal_only_bridge;
    get_streaming(&pedal_only_bridge, &pedal_only_config);
    bridge_host_unmounted(&pedal_only_bridge, 200);
    CHECK(!bridge_requires_full_neutral(&pedal_only_bridge));
    bridge_build_report(&pedal_only_bridge, &pedal, false, report);
    CHECK(report[4] == 0 && report[5] == 255);
}

static void blocked(void) {
    bridge_config_t config;
    bridge_defaults(&config);
    bridge_t bridge;
    get_streaming(&bridge, &config);
    pedal_t pedal = ready_pedal();
    pedal.output[0] = 65535;
    pedal.output[1] = 65535;
    uint8_t report[20];
    bridge_build_report(&bridge, &pedal, true, report);
    expect_all_zero(report);

    pedal.mode = PEDAL_KEYBOARD;
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);
    pedal.mode = PEDAL_JOYSTICK;

    pedal.calibration_axis = 0;
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);
    pedal.calibration_axis = -1;

    pedal.armed = false;
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);
    pedal.armed = true;

    pedal.sample_valid = false;
    bridge_build_report(&bridge, &pedal, false, report);
    expect_all_zero(report);

    bridge_build_report(&bridge, NULL, false, report);
    expect_all_zero(report);
}

static void quantize(void) {
    CHECK(xinput_axis_quantize(0) == 0);
    CHECK(xinput_axis_quantize(128) == 0);
    CHECK(xinput_axis_quantize(129) == 1);
    CHECK(xinput_axis_quantize(32768) == 128);
    CHECK(xinput_axis_quantize(65535) == 255);
    uint8_t previous = 0;
    for (uint32_t value = 0; value <= 65535u; value += 17u) {
        uint8_t current = xinput_axis_quantize((uint16_t)value);
        CHECK(current >= previous);
        previous = current;
    }
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "pedal_only")) pedal_only();
    else if (!strcmp(argv[1], "handshake")) handshake();
    else if (!strcmp(argv[1], "override")) override();
    else if (!strcmp(argv[1], "max")) max_merge();
    else if (!strcmp(argv[1], "timeout")) timeout();
    else if (!strcmp(argv[1], "unmount")) unmount();
    else if (!strcmp(argv[1], "blocked")) blocked();
    else if (!strcmp(argv[1], "quantize")) quantize();
    else return 2;
    puts("PASS");
    return 0;
}
