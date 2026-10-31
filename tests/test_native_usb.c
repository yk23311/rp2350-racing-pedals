#include "usb.h"
#include "xinput_device.h"
#include "xinput_protocol.h"
#include "tusb.h"
#include "pico/unique_id.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) {fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
void tud_hid_report_complete_cb(uint8_t instance,const uint8_t *report,uint16_t length);
void tud_suspend_cb(bool enabled);
void tud_resume_cb(void);
const uint8_t *tud_descriptor_device_cb(void);
const uint8_t *tud_descriptor_configuration_cb(uint8_t index);
const uint8_t *tud_hid_descriptor_report_cb(uint8_t instance);
const uint16_t *tud_descriptor_string_cb(uint8_t index,uint16_t langid);
uint16_t tud_hid_get_report_cb(uint8_t,uint8_t,hid_report_type_t,uint8_t*,uint16_t);
static uint64_t now;
static bool in_busy,key_busy,suspended;
static uint8_t native[20],keys[8];
bool tusb_init(void) {return true;}
void tud_task(void) {}
bool tud_ready(void) {return !suspended;}
bool tud_mounted(void) {return true;}
bool tud_suspended(void) {return suspended;}
uint64_t time_us_64(void) {return now;}
void pico_get_unique_board_id(pico_unique_board_id_t *id) {memset(id->id,7,8);}
void pico_get_unique_board_id_string(char *buffer,size_t n) {snprintf(buffer,n,"0707070707070707");}
bool xinput_device_ready(void) {return !in_busy;}
bool xinput_device_send(const uint8_t report[20]) {CHECK(!in_busy);memcpy(native,report,20);in_busy=true;return true;}
void xinput_device_task(void) {}
void xinput_device_set_serial(uint32_t serial) {CHECK(serial==0x07070707u);}
bool tud_hid_n_ready(uint8_t instance) {CHECK(instance==0);return !key_busy;}
bool tud_hid_n_report(uint8_t instance,uint8_t id,const void *r,uint16_t n) {
    CHECK(instance==0 && id==0 && n==8 && !key_busy);memcpy(keys,r,8);key_busy=true;return true;
}
static void tick(void) {now+=1000;pedal_usb_task();}
static void ack_native(bool success) {in_busy=false;xinput_device_report_complete(success);}
static void ack_keys(void) {key_busy=false;tud_hid_report_complete_cb(0,keys,8);}
static void sample(pedal_t *p,uint16_t n) {uint16_t values[2]={n,n};pedal_sample(p,values);}
int main(void) {
    pedal_config_t c;pedal_defaults(&c);
    for(unsigned i=0;i<2;i++) {c.axis[i].released=500;c.axis[i].pressed=3500;c.axis[i].window=1;c.axis[i].gamma=100;c.axis[i].calibrated=true;}
    pedal_t p;pedal_init(&p,&c);pedal_usb_init(&p);sample(&p,500);
    CHECK(tud_descriptor_device_cb()==xinput_device_descriptor);
    CHECK(tud_descriptor_configuration_cb(0)==xinput_configuration_descriptor && !tud_descriptor_configuration_cb(1));
    CHECK(tud_hid_descriptor_report_cb(0) && !tud_hid_descriptor_report_cb(1));
    CHECK(tud_descriptor_string_cb(0xee,0)==xinput_os_string);
    tick();CHECK(native[1]==20 && !native[4] && !native[5]);
    ack_native(true);sample(&p,3500);tick();CHECK(!native[4] && !native[5]); /* keyboard neutral not ACKed */
    ack_native(true);ack_keys();CHECK(pedal_usb_quiet());
    tick();CHECK(native[4]==255 && native[5]==255);ack_native(true);ack_keys();
    uint8_t report[20];CHECK(tud_hid_get_report_cb(0,0,HID_REPORT_TYPE_INPUT,report,20)==8);
    CHECK(!report[2] && !report[3]);xinput_device_get_report(report);CHECK(report[4]==255 && report[5]==255);
    pedal_mode(&p,PEDAL_KEYBOARD);sample(&p,500);tick();CHECK(!native[4] && !native[5]);ack_native(true);ack_keys();
    sample(&p,3500);tick();CHECK(!native[4] && !native[5] && keys[2]==26 && keys[3]==22);ack_native(true);ack_keys();
    pedal_mode(&p,PEDAL_JOYSTICK);sample(&p,500);tick();ack_native(true);ack_keys();sample(&p,3500);tick();CHECK(native[5]==255);
    ack_native(false);ack_keys();CHECK(!p.armed);tick();CHECK(!native[5]);ack_native(true);ack_keys();
    sample(&p,3500);tick();CHECK(!native[5]);ack_native(true);ack_keys();sample(&p,500);sample(&p,3500);tick();CHECK(native[5]==255);
    ack_native(true);ack_keys();suspended=true;tud_suspend_cb(false);CHECK(!p.armed);
    suspended=false;tud_resume_cb();sample(&p,3500);tick();CHECK(!native[5]);
    puts("PASS: native USB callbacks, keyboard instance, neutral barrier, retries and resume");return 0;
}
