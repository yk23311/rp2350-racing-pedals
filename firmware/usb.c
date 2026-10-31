#include "usb.h"
#include "usb_layout.h"
#include "report_gate.h"
#if PEDAL_USB_XINPUT
#include "xinput_device.h"
#include "xinput_protocol.h"
#endif
#include "tusb.h"
#include "pico/unique_id.h"
#include "pico/time.h"
#include <string.h>
static pedal_t *state;
static report_gate_t gate;
static uint32_t generation;
static uint64_t next_report;
static void restart(void) {
    pedal_reset(state); generation=state->generation;
    memset(&gate,0,sizeof(gate)); report_gate_reset(&gate);
    next_report=0;
}
void pedal_usb_init(pedal_t *pedal) {
    state=pedal; restart();
#if PEDAL_USB_XINPUT
    pico_unique_board_id_t id; pico_get_unique_board_id(&id);
    uint32_t serial=0; for(unsigned i=0;i<4;i++)serial|=(uint32_t)id.id[i+4]<<(8*i);
    xinput_device_set_serial(serial);
#endif
#if PEDAL_USB_HOST
    tusb_rhport_init_t init = {.role=TUSB_ROLE_DEVICE,.speed=TUSB_SPEED_FULL};
    tusb_init(0,&init);
#else
    tusb_init();
#endif
}
bool pedal_usb_quiet(void) { return tud_mounted() && !tud_suspended() && generation==state->generation && report_gate_quiet(&gate); }
static void make_report(unsigned itf,uint8_t data[20]) {
    memset(data,0,20);
    bool blocked=report_gate_blocked(&gate) || generation!=state->generation;
#if PEDAL_USB_XINPUT
    if(itf==0) { xinput_report_build(state,blocked,data);return; }
#endif
    if(blocked || !state->armed || state->calibration_axis>=0) return;
    if(itf==0 && state->mode==PEDAL_JOYSTICK) {
        data[0]=(uint8_t)state->output[0]; data[1]=(uint8_t)(state->output[0]>>8);
        data[2]=(uint8_t)state->output[1]; data[3]=(uint8_t)(state->output[1]>>8);
    } else if(itf==1) pedal_keyboard(state,data);
}
void pedal_usb_task(void) {
    tud_task();
    if(generation!=state->generation) { generation=state->generation; report_gate_reset(&gate); }
    if(!tud_mounted() || tud_suspended()) return;
#if PEDAL_USB_XINPUT
    xinput_device_task();
#endif
    uint64_t now=time_us_64(); if(now<next_report) return;
    next_report=now+1000;
    for(unsigned i=0;i<2;i++) {
        uint8_t hid_instance=(uint8_t)i;
        unsigned len=i?8:4,first=0;
#if PEDAL_USB_XINPUT
        hid_instance=0;
        if(i==0) { len=20;first=2;if(!xinput_device_ready())continue; }
        else if(!tud_hid_n_ready(hid_instance))continue;
#else
        if(!tud_hid_n_ready(hid_instance))continue;
#endif
        if(gate.busy[i])continue;
        uint8_t data[20]; make_report(i,data);
        bool neutral=true; for(unsigned j=first;j<len;j++) if(data[j]) neutral=false;
        if(!report_gate_begin(&gate,i,neutral))continue;
        bool sent;
#if PEDAL_USB_XINPUT
        if(i==0)sent=xinput_device_send(data);
        else
#endif
        sent=tud_hid_n_report(hid_instance,0,data,(uint16_t)len);
        if(!sent)gate.busy[i]=false;
    }
}
void tud_mount_cb(void) { restart(); }
void tud_umount_cb(void) { restart(); }
void tud_suspend_cb(bool remote_wakeup_en) { (void)remote_wakeup_en; restart(); }
void tud_resume_cb(void) { restart(); }
void tud_hid_report_complete_cb(uint8_t instance,const uint8_t *report,uint16_t len) {
    (void)report; (void)len;
#if PEDAL_USB_XINPUT
    if(instance==0)report_gate_complete(&gate,1);
#else
    report_gate_complete(&gate,instance);
#endif
}
#if PEDAL_USB_XINPUT
void xinput_device_get_report(uint8_t report[20]) { make_report(0,report); }
void xinput_device_report_complete(bool success) {
    if(success)report_gate_complete(&gate,0);
    else { gate.busy[0]=false;pedal_reset(state); }
}
#endif
uint16_t tud_hid_get_report_cb(uint8_t instance,uint8_t report_id,hid_report_type_t type,uint8_t *buffer,uint16_t requested) {
    if(report_id!=0 || type!=HID_REPORT_TYPE_INPUT)return 0;
    uint8_t data[20]; uint16_t len;
#if PEDAL_USB_XINPUT
    if(instance!=0)return 0;
    make_report(1,data);len=8;
#else
    if(instance>=2)return 0;
    make_report(instance,data);len=instance?8:4;
#endif
    if(len>requested) len=requested;
    memcpy(buffer,data,len); return len;
}
void tud_hid_set_report_cb(uint8_t instance,uint8_t report_id,hid_report_type_t type,const uint8_t *buffer,uint16_t len) {
    (void)instance;(void)report_id;(void)type;(void)buffer;(void)len;
}
const uint8_t *tud_descriptor_device_cb(void) {
#if PEDAL_USB_XINPUT
    return xinput_device_descriptor;
#else
    return usb_device_descriptor;
#endif
}
const uint8_t *tud_descriptor_configuration_cb(uint8_t index) {
    if(index!=0)return NULL;
#if PEDAL_USB_XINPUT
    return xinput_configuration_descriptor;
#else
    return usb_configuration_descriptor;
#endif
}
const uint8_t *tud_hid_descriptor_report_cb(uint8_t instance) {
#if PEDAL_USB_XINPUT
    return instance==0?usb_keyboard_descriptor:NULL;
#else
    return instance==0?usb_joystick_descriptor:instance==1?usb_keyboard_descriptor:NULL;
#endif
}
const uint16_t *tud_descriptor_string_cb(uint8_t index,uint16_t langid) {
    (void)langid; static uint16_t out[33]; char serial[2*PICO_UNIQUE_BOARD_ID_SIZE_BYTES+1];
#if PEDAL_USB_XINPUT
    if(index==0xee)return xinput_os_string;
    const char *strings[]={"","DIY Pedals","RP2350 Native XInput Pedals",serial};
#else
    const char *strings[]={"","DIY Pedals","RP2350 Dual Pedals",serial};
#endif
    if(index==0) { out[0]=0x0304;out[1]=0x0409;return out; }
    if(index>=4) return NULL;
    if(index==3) pico_get_unique_board_id_string(serial,sizeof(serial));
    size_t len=strlen(strings[index]);if(len>32)len=32;
    for(size_t i=0;i<len;i++) out[i+1]=(uint8_t)strings[index][i];
    out[0]=(uint16_t)(0x0300u|((len+1)*2));return out;
}
