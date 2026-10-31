#include "usb.h"
#include "host.h"
#include "console.h"
#include "control_profile.h"
#include "xinput_device.h"
#include "tusb.h"
#include "pico/unique_id.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if(!(x)) { fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#x);exit(1); } } while(0)
void tud_hid_report_complete_cb(uint8_t instance,const uint8_t *report,uint16_t length);
static uint64_t now;
static bool in_busy,key_busy;
static uint8_t native[20],keys[8];
static bridge_t host;
static unsigned saves;

const bridge_t *host_bridge(void) { return &host; }
bool tusb_init(uint8_t rhport,const tusb_rhport_init_t *init) {
    CHECK(rhport==0 && init->role==TUSB_ROLE_DEVICE && init->speed==TUSB_SPEED_FULL);return true;
}
void tud_task(void) {}
bool tud_ready(void) { return true; }
bool tud_mounted(void) { return true; }
bool tud_suspended(void) { return false; }
uint64_t time_us_64(void) { return now; }
void pico_get_unique_board_id(pico_unique_board_id_t *id) { memset(id->id,7,8); }
void pico_get_unique_board_id_string(char *buffer,size_t n) { snprintf(buffer,n,"0707070707070707"); }
bool xinput_device_ready(void) { return !in_busy; }
bool xinput_device_send(const uint8_t report[20]) {
    CHECK(!in_busy);memcpy(native,report,20);in_busy=true;return true;
}
void xinput_device_task(void) {}
void xinput_device_set_serial(uint32_t serial) { CHECK(serial==0x07070707u); }
bool tud_hid_n_ready(uint8_t instance) { CHECK(instance==0);return !key_busy; }
bool tud_hid_n_report(uint8_t instance,uint8_t id,const void *report,uint16_t length) {
    CHECK(instance==0 && id==0 && length==8 && !key_busy);
    memcpy(keys,report,8);key_busy=true;return true;
}
static void tick(void) { now+=1000;pedal_usb_task(); }
static void ack_native(void) { CHECK(in_busy);in_busy=false;xinput_device_report_complete(true); }
static void ack_keys(void) { CHECK(key_busy);key_busy=false;tud_hid_report_complete_cb(0,keys,8); }
static void ack(void) { ack_native();ack_keys(); }
static void sample(pedal_t *pedal,uint16_t throttle,uint16_t brake) {
    uint16_t raw[2]={throttle,brake};pedal_sample(pedal,raw);
}
static void neutral(void) {
    CHECK(native[0]==0 && native[1]==20);
    for(unsigned i=2;i<20;i++) CHECK(native[i]==0);
}
static void report(const xinput_pad_t *pad) { bridge_host_report(&host,pad,(uint32_t)(now/1000)); }
static void mount(void) {
    bridge_host_mounted(&host,0x20bc,0x5128,(uint32_t)(now/1000));
    bridge_host_handshake_done(&host,(uint32_t)(now/1000));
}
static void init(pedal_t *pedal) {
    bridge_config_t bridge_config;bridge_defaults(&bridge_config);bridge_config.merge_mode=BRIDGE_MERGE_MAX;
    bridge_init(&host,&bridge_config,0);mount();
    xinput_pad_t pad={0};report(&pad);report(&pad);CHECK(bridge_host_ready(&host));
    pedal_config_t config;pedal_defaults(&config);
    for(unsigned i=0;i<2;i++) {
        config.axis[i].released=500;config.axis[i].pressed=3500;config.axis[i].window=1;
        config.axis[i].gamma=100;config.axis[i].calibrated=true;
    }
    pedal_init(pedal,&config);pedal_usb_init(pedal);
    tick();neutral();sample(pedal,500,500);ack();
    tick();neutral();ack();CHECK(pedal_usb_quiet());
}
static int16_t axis(unsigned offset) { return (int16_t)((uint16_t)native[offset]|((uint16_t)native[offset+1]<<8)); }
static void combined(void) {
    pedal_t pedal;init(&pedal);
    xinput_pad_t pad={.buttons=0x9401,.lt=15,.rt=37,.lx=-20000,.ly=12345,.rx=6789,.ry=-1234};
    report(&pad);sample(&pedal,3500,2000);tick();
    CHECK(native[2]==0x01 && native[3]==0x90 && native[4]==126 && native[5]==255); /* reserved bit10 filtered */
    CHECK(axis(6)==-20000 && axis(8)==12345 && axis(10)==6789 && axis(12)==-1234);ack();
}
static void barrier(void) {
    pedal_t pedal;init(&pedal);
    pedal_reset(&pedal);sample(&pedal,500,500);
    xinput_pad_t pad={.buttons=0x1000,.rt=200,.lx=12000};report(&pad);
    tick();neutral();ack_native();
    sample(&pedal,3500,3500);tick();neutral(); /* Keyboard neutral still in flight. */
    ack_native();ack_keys();xinput_pad_t zero={0};report(&zero);tick();ack();
    report(&pad);tick();
    CHECK(native[3]==0x10 && native[4]==255 && native[5]==255 && axis(6)==12000);ack();
}
static void reconnect(pedal_t *pedal) {
    xinput_pad_t zero={0},active={.buttons=0x1000,.rt=200,.lx=12000};
    mount();report(&active);CHECK(!bridge_host_ready(&host));
    tick();neutral();ack();
    report(&zero);tick();neutral();ack();CHECK(!bridge_host_ready(&host));
    report(&zero);CHECK(bridge_host_ready(&host));
    tick();neutral();ack(); /* STREAMING transition resets pedal arming and both USB gates. */
    sample(pedal,3500,3500);tick();neutral();ack();CHECK(!pedal->armed);
    sample(pedal,500,500);sample(pedal,3500,3500);report(&active);tick();
    CHECK(native[3]==0x10 && native[4]==255 && native[5]==255 && axis(6)==12000);ack();
}
static void faults(void) {
    pedal_t pedal;init(&pedal);
    xinput_pad_t active={.buttons=0x1000,.rt=200,.lx=12000};
    sample(&pedal,3500,3500);report(&active);tick();CHECK(native[5]==255);ack();
    bridge_host_unmounted(&host,(uint32_t)(now/1000));tick();neutral();ack();
    sample(&pedal,3500,3500);tick();neutral();ack();reconnect(&pedal);
    now+=(BRIDGE_HOST_TIMEOUT_MS+1u)*1000u;bridge_tick(&host,(uint32_t)(now/1000));
    CHECK(host.state==BRIDGE_HOST_STALE);tick();neutral();ack();
    sample(&pedal,3500,3500);tick();neutral();ack();
    xinput_pad_t zero={0};report(&zero);tick();neutral();ack();CHECK(!bridge_host_ready(&host));
    report(&zero);tick();neutral();ack();CHECK(bridge_host_ready(&host));
    sample(&pedal,500,500);sample(&pedal,3500,3500);report(&active);tick();CHECK(native[5]==255);ack();
}
static bool save_config(void *context,const pedal_config_t *config) {
    (void)context;(void)config;
    if(!pedal_usb_quiet()) return false;
    saves++;return true;
}
static void save_sticks(void) {
    pedal_t pedal;init(&pedal);
    xinput_pad_t drift={.lx=-928,.ly=704,.rx=91,.ry=-103};report(&drift);tick();
    CHECK(axis(6)==-928 && axis(8)==704);ack();CHECK(pedal_usb_quiet());
    char response[CONSOLE_RESPONSE_SIZE];console_execute(&pedal,"SAVE",save_config,NULL,response);
    CHECK(!strcmp(response,"OK\n") && saves==1);
}
static void save_latest(bool trigger) {
    pedal_t pedal;init(&pedal);CHECK(pedal_usb_quiet());
    xinput_pad_t active={0};if(trigger) active.rt=200;else active.buttons=0x1000;
    report(&active); /* host_task received input after the last USB neutral ACK, before next USB task. */
    CHECK(!in_busy && !key_busy);
    char response[CONSOLE_RESPONSE_SIZE];console_execute(&pedal,"SAVE",save_config,NULL,response);
    CHECK(!strcmp(response,"ERR STATE_OR_VALUE\n") && saves==0);
    if(trigger) {
        active.rt=0;active.lt=200;report(&active);
        console_execute(&pedal,"SAVE",save_config,NULL,response);
        CHECK(!strcmp(response,"ERR STATE_OR_VALUE\n") && saves==0);
    }
}
static void mapped_controls(void) {
    pedal_t pedal;init(&pedal);
    char response[CONSOLE_RESPONSE_SIZE];
    console_execute(&pedal,"BIND 10 1 4",save_config,NULL,response);
    CHECK(!strcmp(response,"OK\n"));
    xinput_pad_t held={.buttons=0x1000};report(&held);sample(&pedal,500,500);
    tick();neutral();ack();tick();neutral();CHECK(!keys[2]);ack(); /* held during apply stays released */
    xinput_pad_t zero={0};report(&zero);tick();ack();
    control_current()->sticks[0].gamma=200;
    control_current()->triggers[1].gamma=200;
    held.lx=16384;held.rt=128;report(&held);tick();
    CHECK(!native[2] && !native[3] && keys[2]==4);
    CHECK(axis(6)>=8190 && axis(6)<=8194 && native[5]>=63 && native[5]<=65);ack();
    bridge_host_unmounted(&host,(uint32_t)(now/1000));tick();neutral();CHECK(!keys[2]);ack();
}
static void save_disabled_source(void) {
    pedal_t pedal;init(&pedal);
    control_current()->bindings[10].kind=2;control_current()->bindings[10].target=0;
    xinput_pad_t held={.buttons=0x1000};report(&held);tick();neutral();ack();
    char response[CONSOLE_RESPONSE_SIZE];console_execute(&pedal,"SAVE",save_config,NULL,response);
    CHECK(!strcmp(response,"ERR STATE_OR_VALUE\n") && saves==0);
}
static void mapped_release_barriers(void) {
    pedal_t pedal;init(&pedal);char response[CONSOLE_RESPONSE_SIZE];xinput_pad_t zero={0},held={.buttons=0x1000};
    console_execute(&pedal,"BIND 10 1 4",save_config,NULL,response);sample(&pedal,500,500);report(&zero);tick();ack();tick();ack();
    report(&held);tick();CHECK(keys[2]==4);ack();
    console_execute(&pedal,"BIND 10 1 5",save_config,NULL,response);sample(&pedal,500,500);tick();CHECK(!keys[2]);ack();
    tick();CHECK(!keys[2]);ack();report(&zero);tick();ack();report(&held);tick();CHECK(keys[2]==5);ack();
    console_execute(&pedal,"CAL 0 BEGIN",save_config,NULL,response);tick();CHECK(!keys[2]);ack();
    console_execute(&pedal,"CAL 0 CANCEL",save_config,NULL,response);sample(&pedal,500,500);tick();CHECK(!keys[2]);ack();
    report(&zero);tick();ack();report(&held);tick();CHECK(keys[2]==5);ack();
    console_execute(&pedal,"MODE KEYBOARD",save_config,NULL,response);sample(&pedal,500,500);tick();CHECK(!keys[2]);ack();
    report(&zero);tick();ack();sample(&pedal,3500,3500);tick();CHECK(keys[2]==26 && keys[3]==22);ack();
    console_execute(&pedal,"MODE JOYSTICK",save_config,NULL,response);sample(&pedal,500,500);tick();ack();report(&held);tick();CHECK(keys[2]==5);ack();
    now+=(BRIDGE_HOST_TIMEOUT_MS+1u)*1000u;bridge_tick(&host,(uint32_t)(now/1000));tick();neutral();CHECK(!keys[2]);ack();
}
bool pedal_usb_console(const char *line,char response[CONSOLE_RESPONSE_SIZE]);
static void telemetry(void) {
    pedal_t pedal;init(&pedal);char response[CONSOLE_RESPONSE_SIZE];
    console_input_t input={0};
    const char *query="CAPS\n";
    while(*query) { bool ready=pedal_usb_feed(&input,*query++,&pedal,save_config,NULL,response);if(!*query) CHECK(ready); }
    CHECK(strstr(response,"\"telemetry\":1"));
    CHECK(pedal_usb_console("CAPS",response));
    CHECK(strstr(response,"\"telemetry\":1") && strstr(response,"\"profile\":1"));
    control_current()->bindings[10]=(control_binding_t){1,4};
    control_current()->sticks[0].gamma=200;control_current()->triggers[1].gamma=200;
    xinput_pad_t active={.buttons=0x1000,.rt=128,.lx=16384};report(&active);tick();
    CHECK(pedal_usb_console("TELEMETRY",response));
    CHECK(strstr(response,"\"raw\":[4096,0,128,16384,0,0,0]"));
    CHECK(strstr(response,"\"processed\":[0,0,64,8192,0,0,0]"));
    CHECK(strstr(response,"\"keys\":[0,0,4,0,0,0,0,0]"));
    CHECK(strlen(response)<CONSOLE_RESPONSE_SIZE-1 && response[strlen(response)-1]=='\n');ack();
    CHECK(!pedal_usb_console("TELEMETRY EXTRA",response));
}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    if(!strcmp(argv[1],"combined"))combined();
    else if(!strcmp(argv[1],"barrier"))barrier();
    else if(!strcmp(argv[1],"faults"))faults();
    else if(!strcmp(argv[1],"save_sticks"))save_sticks();
    else if(!strcmp(argv[1],"save_button"))save_latest(false);
    else if(!strcmp(argv[1],"save_trigger"))save_latest(true);
    else if(!strcmp(argv[1],"mapped"))mapped_controls();
    else if(!strcmp(argv[1],"save_source"))save_disabled_source();
    else if(!strcmp(argv[1],"mapped_release"))mapped_release_barriers();
    else if(!strcmp(argv[1],"telemetry"))telemetry();
    else return 2;
    puts("PASS: real Host bridge USB integration");return 0;
}
