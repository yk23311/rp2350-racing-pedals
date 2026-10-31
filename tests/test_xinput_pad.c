#include "xinput_pad.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x);exit(1); } } while(0)

static void parse(void) {
    const uint8_t raw[20] = {0x00,0x14,0x01,0x00,0x0A,0x14,0x00,0x00,
                             0x00,0x80,0xFF,0x7F,0x34,0x12,0,0,0,0,0,0};
    xinput_pad_t pad;
    memset(&pad, 0xA5, sizeof(pad));
    CHECK(xinput_pad_parse_wired(raw, 20, &pad));
    CHECK(pad.buttons == 0x0001);
    CHECK(pad.lt == 10 && pad.rt == 20);
    CHECK(pad.lx == 0 && pad.ly == -32768);
    CHECK(pad.rx == 32767 && pad.ry == 0x1234);

    uint8_t longer[32]; memset(longer, 0xCC, sizeof(longer)); memcpy(longer, raw, 20);
    CHECK(xinput_pad_parse_wired(longer, sizeof(longer), &pad));
    CHECK(pad.buttons == 1 && pad.rt == 20);

    uint8_t bad[20]; memcpy(bad, raw, 20);
    bad[1] = 0x13;
    xinput_pad_t before = pad;
    CHECK(!xinput_pad_parse_wired(bad, 20, &pad));
    CHECK(memcmp(&before, &pad, sizeof(pad)) == 0);

    memcpy(bad, raw, 20); bad[0] = 0x01;
    CHECK(!xinput_pad_parse_wired(bad, 20, &pad));
    CHECK(!xinput_pad_parse_wired(raw, 19, &pad));
    CHECK(!xinput_pad_parse_wired(NULL, 20, &pad));
    CHECK(!xinput_pad_parse_wired(raw, 20, NULL));

    xinput_pad_clear(&pad);
    CHECK(pad.buttons == 0 && pad.lt == 0 && pad.rt == 0 &&
          pad.lx == 0 && pad.ly == 0 && pad.rx == 0 && pad.ry == 0);
    xinput_pad_clear(NULL);
}

static xinput_pad_t make_pad(int16_t lx, int16_t ly, uint16_t buttons, uint8_t lt, uint8_t rt) {
    xinput_pad_t pad; memset(&pad, 0, sizeof(pad));
    pad.lx = lx; pad.ly = ly; pad.buttons = buttons; pad.lt = lt; pad.rt = rt;
    return pad;
}

static void neutral(void) {
    xinput_pad_t pad = make_pad(-928, 704, 0, 0, 0);
    CHECK(xinput_pad_is_neutral(&pad, 4000));
    CHECK(xinput_pad_is_neutral(&pad, 928));
    CHECK(!xinput_pad_is_neutral(&pad, 927));

    pad.lx = 4000; CHECK(xinput_pad_is_neutral(&pad, 4000));
    pad.lx = 4001; CHECK(!xinput_pad_is_neutral(&pad, 4000));
    pad.lx = -4001; CHECK(!xinput_pad_is_neutral(&pad, 4000));
    pad.lx = 0; pad.ly = 32767; CHECK(!xinput_pad_is_neutral(&pad, 4000));
    pad.ly = -32768; CHECK(!xinput_pad_is_neutral(&pad, 4000));

    pad = make_pad(0, 0, 1, 0, 0); CHECK(!xinput_pad_is_neutral(&pad, 4000));
    pad = make_pad(0, 0, 0, 1, 0); CHECK(!xinput_pad_is_neutral(&pad, 4000));
    pad = make_pad(0, 0, 0, 0, 1); CHECK(!xinput_pad_is_neutral(&pad, 4000));
    CHECK(!xinput_pad_is_neutral(NULL, 4000));
}

static void predicates(void) {
    xinput_pad_t pad = make_pad(-928, 704, 0, 0, 0);
    CHECK(xinput_pad_buttons_triggers_neutral(&pad));
    pad.buttons = 0x1000; CHECK(!xinput_pad_buttons_triggers_neutral(&pad));
    pad.buttons = 0; pad.lt = 1; CHECK(!xinput_pad_buttons_triggers_neutral(&pad));
    pad.lt = 0; pad.rt = 1; CHECK(!xinput_pad_buttons_triggers_neutral(&pad));
    CHECK(!xinput_pad_buttons_triggers_neutral(NULL));
    xinput_pad_clear(&pad);
    CHECK(xinput_pad_buttons_triggers_neutral(&pad));
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "parse")) parse();
    else if (!strcmp(argv[1], "neutral")) neutral();
    else if (!strcmp(argv[1], "predicates")) predicates();
    else return 2;
    puts("PASS");
    return 0;
}
