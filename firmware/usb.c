#include "usb.h"
#include "usb_layout.h"
#include "report_gate.h"
#ifndef PEDAL_USB_HOST
#define PEDAL_USB_HOST 0
#endif
#if PEDAL_USB_XINPUT
#include "xinput_device.h"
#include "xinput_protocol.h"
#endif
#if PEDAL_USB_HOST
#include "host.h"
#include "control_profile.h"
#endif
#include "tusb.h"
#include "pico/unique_id.h"
#include "pico/time.h"
#include <string.h>
#include <stdio.h>
static pedal_t *state;
static report_gate_t gate;
static uint32_t generation;
static uint64_t next_report;
#if PEDAL_USB_HOST
static bridge_host_state_t last_host_state;
static bool last_host_seen;
static bool last_xinput_controlled_neutral;
static bool pending_xinput_controlled_neutral;
static bool host_controls_released;
#endif
static void restart(void) {
    pedal_reset(state); generation=state->generation;
    memset(&gate,0,sizeof(gate)); report_gate_reset(&gate);
    next_report=0;
#if PEDAL_USB_HOST
    last_xinput_controlled_neutral=false;
    pending_xinput_controlled_neutral=false;
    host_controls_released=false;
#endif
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
bool pedal_usb_quiet(void) {
#if PEDAL_USB_HOST
    uint8_t current[20];
    bridge_build_report(host_bridge(),state,false,current);
    bool current_quiet=!current[2] && !current[3] && !current[4] && !current[5];
    bool gate_quiet=!report_gate_blocked(&gate) && !gate.busy[0] && !gate.busy[1] &&
                    gate.last_neutral[1] && last_xinput_controlled_neutral && current_quiet;
    if(host_bridge()->pad_valid && !xinput_pad_buttons_triggers_neutral(&host_bridge()->pad)) gate_quiet=false;
    return tud_mounted() && !tud_suspended() && generation==state->generation && gate_quiet;
#else
    return tud_mounted() && !tud_suspended() && generation==state->generation && report_gate_quiet(&gate);
#endif
}
static void make_report(unsigned itf,uint8_t data[20]) {
    memset(data,0,20);
    bool blocked=report_gate_blocked(&gate) || generation!=state->generation;
#if PEDAL_USB_HOST
    blocked=blocked || !host_controls_released;
#endif
#if PEDAL_USB_XINPUT
#if PEDAL_USB_HOST
    if(itf==0) { bridge_build_report(host_bridge(),state,blocked,data);return; }
#else
    if(itf==0) { xinput_report_build(state,blocked,data);return; }
#endif
#endif
    if(blocked || !state->armed || state->calibration_axis>=0) return;
    if(itf==0 && state->mode==PEDAL_JOYSTICK) {
        data[0]=(uint8_t)state->output[0]; data[1]=(uint8_t)(state->output[0]>>8);
        data[2]=(uint8_t)state->output[1]; data[3]=(uint8_t)(state->output[1]>>8);
    } else if(itf==1) {
        pedal_keyboard(state,data);
#if PEDAL_USB_HOST
        if(state->mode==PEDAL_JOYSTICK && state->sample_valid && bridge_host_ready(host_bridge())) {
            xinput_pad_t processed;
            control_transform(control_current(),&host_bridge()->pad,&processed,data);
        }
#endif
    }
}
bool pedal_usb_console(const char *line,char response[CONSOLE_RESPONSE_SIZE]) {
    if(!strcmp(line,"CAPS")) {
        snprintf(response,CONSOLE_RESPONSE_SIZE,
            "OK {\"control_center\":1,\"profile\":%d,\"telemetry\":%d,\"bridge\":%d,\"version\":\"%s\",\"persist_format\":%d}\n",
            PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,
            PEDAL_USB_HOST?"0.4.0":(PEDAL_USB_XINPUT?"0.2.0":"0.1.0"),PEDAL_USB_HOST?2:1);
        return true;
    }
#if PEDAL_USB_HOST
    if(!strcmp(line,"TELEMETRY")) {
        const bridge_t *host=host_bridge();
        xinput_pad_t raw=host->pad,processed={0}; uint8_t ignored[8],keys[20],output[20];
        if(!host->pad_valid) xinput_pad_clear(&raw);
        control_transform(control_current(),&raw,&processed,ignored);
        make_report(0,output);make_report(1,keys);
        char a[100],b[100];
        snprintf(a,sizeof(a),"[%u,%u,%u,%d,%d,%d,%d]",raw.buttons,raw.lt,raw.rt,raw.lx,raw.ly,raw.rx,raw.ry);
        snprintf(b,sizeof(b),"[%u,%u,%u,%d,%d,%d,%d]",processed.buttons,processed.lt,processed.rt,processed.lx,processed.ly,processed.rx,processed.ry);
        xinput_pad_t out; (void)xinput_pad_parse_wired(output,20,&out);
        bool blocked=report_gate_blocked(&gate) || generation!=state->generation || !host_controls_released;
        snprintf(response,CONSOLE_RESPONSE_SIZE,
            "OK {\"raw\":%s,\"processed\":%s,\"output\":[%u,%u,%u,%d,%d,%d,%d],"
            "\"keys\":[%u,%u,%u,%u,%u,%u,%u,%u],\"state\":%d,\"age\":%lu,\"reports\":%lu,\"timeouts\":%lu,"
            "\"blocked\":%s,\"keyboard_rollover\":%s,\"fresh\":%s}\n",
            a,b,out.buttons,out.lt,out.rt,out.lx,out.ly,out.rx,out.ry,
            keys[0],keys[1],keys[2],keys[3],keys[4],keys[5],keys[6],keys[7],(int)host->state,
            (unsigned long)(host->pad_valid?(uint32_t)(time_us_64()/1000)-host->last_report_ms:0),
            (unsigned long)host->valid_reports,(unsigned long)host->timeouts,
            blocked?"true":"false",keys[2]==1?"true":"false",bridge_host_ready(host)?"true":"false");
        return true;
    }
#endif
    return false;
}
bool pedal_usb_feed(console_input_t *input,char ch,pedal_t *pedal,console_save_fn save,void *context,char response[CONSOLE_RESPONSE_SIZE]) {
    if(!console_feed(input,ch,pedal,save,context,response)) return false;
    if(!strcmp(response,"ERR COMMAND\n") || !strcmp(response,"ERR STATE_OR_VALUE\n"))
        (void)pedal_usb_console(input->line,response);
    return true;
}
void pedal_usb_task(void) {
#if PEDAL_USB_HOST
    const bridge_t *host=host_bridge();
    if(host->state!=last_host_state || host->host_seen!=last_host_seen) {
        last_host_state=host->state; last_host_seen=host->host_seen; restart();
    }
#endif
    tud_task();
    if(generation!=state->generation) {
        generation=state->generation; report_gate_reset(&gate);
#if PEDAL_USB_HOST
        host_controls_released=false;
#endif
    }
#if PEDAL_USB_HOST
    if(!host->host_seen || (bridge_host_ready(host) && xinput_pad_is_neutral(&host->pad,BRIDGE_STICK_TOLERANCE)))
        host_controls_released=true;
#endif
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
        if(i==0) {
#if PEDAL_USB_HOST
            pending_xinput_controlled_neutral=!data[2] && !data[3] && !data[4] && !data[5];
#endif
            sent=xinput_device_send(data);
        } else
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
#if PEDAL_USB_HOST
    if(success) last_xinput_controlled_neutral=pending_xinput_controlled_neutral;
    else last_xinput_controlled_neutral=false;
    pending_xinput_controlled_neutral=false;
#endif
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
#if PEDAL_USB_HOST
    if(index==0xee)return xinput_os_string;
    const char *strings[]={"","DIY Pedals","RP2350 XInput Bridge",serial};
#elif PEDAL_USB_XINPUT
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
