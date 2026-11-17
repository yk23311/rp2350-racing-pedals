#include "usb.h"
#include "usb_layout.h"
#include "bridge.h"
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
static bool boot_pending;
static bool boot_ack_seen;
static uint64_t boot_requested_at,boot_ack_at;
static enum { SWITCH_IDLE, SWITCH_ACK, SWITCH_DETACHED } switch_phase;
static bool requested_wheel, switch_ack_seen;
static uint64_t switch_requested_at, switch_ack_at, switch_detached_at;
static const tusb_rhport_init_t device_init={.role=TUSB_ROLE_DEVICE,.speed=TUSB_SPEED_FULL};

bool pedal_usb_switch_pending(void) { return switch_phase==SWITCH_ACK; }
bool pedal_usb_wheel_mode(void) { return control_current()->wheel_mode!=0; }
#define XINPUT_ACTIVE (!pedal_usb_wheel_mode())
#else
#define XINPUT_ACTIVE (PEDAL_USB_XINPUT)
#endif
static void restart(void) {
    pedal_reset(state); generation=state->generation;
    memset(&gate,0,sizeof(gate)); report_gate_reset(&gate);
    next_report=0;
#if PEDAL_USB_HOST
    last_xinput_controlled_neutral=false;
    pending_xinput_controlled_neutral=false;
    host_controls_released=false;
    host_rumble_enable(false);host_rumble_stop();
#endif
}
void pedal_usb_init(pedal_t *pedal) {
#if PEDAL_USB_HOST
    boot_pending=boot_ack_seen=false;boot_requested_at=boot_ack_at=0;
    switch_phase=SWITCH_IDLE;
#endif
    state=pedal; restart();
#if PEDAL_USB_XINPUT
    pico_unique_board_id_t id; pico_get_unique_board_id(&id);
    uint32_t serial=0; for(unsigned i=0;i<4;i++)serial|=(uint32_t)id.id[i+4]<<(8*i);
    xinput_device_set_serial(serial);
#endif
#if PEDAL_USB_HOST
    tusb_init(0,&device_init);
#else
    tusb_init();
#endif
}
#if PEDAL_USB_HOST
void pedal_usb_switch_task(bool response_acked) {
    uint64_t now=time_us_64();
    if(switch_phase==SWITCH_DETACHED) {
        if(now-switch_detached_at<300000) return;
        control_current()->wheel_mode=requested_wheel;
        pedal_mode(state,PEDAL_JOYSTICK);
        restart();
        tusb_init(0,&device_init);
        switch_phase=SWITCH_IDLE;
        return;
    }
    if(switch_phase!=SWITCH_ACK) return;
    if(!response_acked) {
        if(now-switch_requested_at>=1500000) {
            switch_phase=SWITCH_IDLE;
            restart();
        }
        return;
    }
    if(!switch_ack_seen) {
        switch_ack_seen=true;
        switch_ack_at=now;
    }
    uint64_t elapsed=now-switch_ack_at;
    host_rumble_status_t rumble;
    host_rumble_status(&rumble);
    if(elapsed<50000 || (elapsed<300000 &&
       (!report_gate_quiet(&gate) || rumble.pending || rumble.in_flight))) return;
    tud_deinit(0);
    switch_detached_at=now;
    switch_phase=SWITCH_DETACHED;
}
#endif
bool pedal_usb_boot_pending(void) {
#if PEDAL_USB_HOST
    return boot_pending;
#else
    return false;
#endif
}
bool pedal_usb_boot_ready(bool response_acked) {
#if PEDAL_USB_HOST
    if(!boot_pending) return false;
    uint64_t elapsed=time_us_64()-boot_requested_at;
    if(!response_acked) {
        if(elapsed>=1500000) {boot_pending=false;restart();}
        return false;
    }
    if(!boot_ack_seen) {boot_ack_seen=true;boot_ack_at=time_us_64();}
    elapsed=time_us_64()-boot_ack_at;
    if(elapsed<300000) return false;
    host_rumble_status_t r;host_rumble_status(&r);
    /* If a cable/receiver fails, ROM USB reset still releases PC inputs.
     * Stop delivery has a finite retry budget; never claim a radio ACK. */
    return (report_gate_quiet(&gate) && !r.pending && !r.in_flight) || elapsed>=1500000;
#else
    (void)response_acked;return false;
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
    blocked=blocked || !host_controls_released || boot_pending || switch_phase!=SWITCH_IDLE;
#endif
#if PEDAL_USB_XINPUT
#if PEDAL_USB_HOST
    if(itf==0) {
        if(XINPUT_ACTIVE) bridge_build_report(host_bridge(),state,blocked,data);
        else bridge_build_wheel_report(host_bridge(),state,blocked,data);
        return;
    }
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
        if(state->mode==PEDAL_KEYBOARD && control_current()->throttle_axis) {
            for(unsigned i=2;i<8;i++) {
                if(data[i]==26) data[i]=22;
                else if(data[i]==22) data[i]=26;
            }
        }
        if(state->mode==PEDAL_JOYSTICK && state->sample_valid && bridge_host_ready(host_bridge())) {
            xinput_pad_t processed;
            control_transform(control_current(),&host_bridge()->pad,&processed,data);
        }
#endif
    }
}
#if PEDAL_USB_HOST
static uint16_t get_u16(const uint8_t *data) {
    return (uint16_t)(data[0]|((uint16_t)data[1]<<8));
}

static bool parse_bounded(const char **cursor,unsigned limit,unsigned *result) {
    const char *p=*cursor;unsigned value=0;
    if(*p<'0' || *p>'9')return false;
    while(*p>='0' && *p<='9') {
        unsigned digit=(unsigned)(*p++-'0');
        if(value>limit/10 || (value==limit/10 && digit>limit%10))return false;
        value=value*10+digit;
    }
    *cursor=p;*result=value;return true;
}
#endif
bool pedal_usb_console(const char *line,char response[CONSOLE_RESPONSE_SIZE]) {
    if(!strcmp(line,"CAPS")) {
        snprintf(response,CONSOLE_RESPONSE_SIZE,
            "OK {\"control_center\":1,\"profile\":%d,\"telemetry\":%d,\"bridge\":%d,\"version\":\"%s\",\"persist_format\":%d,\"rumble\":%d,\"rumble_test\":%d,\"bootsel\":%d,\"pedal_map\":%d,\"wheel\":%d,\"usb_mode\":\"%s\"}\n",
            PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,
            PEDAL_USB_HOST?"0.6.0":(PEDAL_USB_XINPUT?"0.2.0":"0.1.0"),PEDAL_USB_HOST?2:1,
            PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,PEDAL_USB_HOST?1:0,
            PEDAL_USB_HOST?1:0,XINPUT_ACTIVE?"XINPUT":(PEDAL_USB_HOST?"WHEEL":"HID"));
        return true;
    }
#if PEDAL_USB_HOST
    if(!strcmp(line,"USBMODE WHEEL") || !strcmp(line,"USBMODE XINPUT")) {
        if(boot_pending || switch_phase!=SWITCH_IDLE || state->calibration_axis>=0) {
            snprintf(response,CONSOLE_RESPONSE_SIZE,"ERR STATE_OR_VALUE\n");return true;
        }
        requested_wheel=!strcmp(line,"USBMODE WHEEL");
        if(requested_wheel==pedal_usb_wheel_mode()) {
            snprintf(response,CONSOLE_RESPONSE_SIZE,"OK {\"usb_switch\":false}\n");return true;
        }
        switch_requested_at=time_us_64();
        switch_ack_seen=false;
        switch_phase=SWITCH_ACK;
        restart();
        snprintf(response,CONSOLE_RESPONSE_SIZE,USB_SWITCH_REPLY);return true;
    }
    if(!strcmp(line,"BOOTSEL")) {
        boot_pending=true;boot_ack_seen=false;boot_requested_at=time_us_64();restart();
        snprintf(response,CONSOLE_RESPONSE_SIZE,"OK {\"bootsel\":true}\n");return true;
    }
    if(!strcmp(line,"RUMBLE STOP")) {
        host_rumble_stop();snprintf(response,CONSOLE_RESPONSE_SIZE,"OK\n");return true;
    }
    if(!strncmp(line,"RUMBLE TEST ",12)) {
        const char *p=line+12;unsigned left,right,duration;
        bool valid=parse_bounded(&p,255,&left) && *p++==' ' &&
                   parse_bounded(&p,255,&right) && *p++==' ' &&
                   parse_bounded(&p,3000,&duration) && !*p && duration>=100;
        bool accepted=valid && !boot_pending && host_rumble_test((uint8_t)left,(uint8_t)right,duration);
        snprintf(response,CONSOLE_RESPONSE_SIZE,accepted?"OK\n":"ERR STATE_OR_VALUE\n");return true;
    }
    if(!strcmp(line,"RUMBLE")) {
        host_rumble_status_t r;host_rumble_status(&r);
        snprintf(response,CONSOLE_RESPONSE_SIZE,
            "OK {\"received\":%lu,\"sent\":%lu,\"errors\":%lu,\"left\":%u,\"right\":%u,\"pending\":%s,\"in_flight\":%s,\"enabled\":%s,\"available\":%s,\"faulted\":%s,\"testing\":%s,\"remaining_ms\":%lu}\n",
            (unsigned long)r.received,(unsigned long)r.sent,(unsigned long)r.errors,r.left,r.right,
            r.pending?"true":"false",r.in_flight?"true":"false",r.enabled?"true":"false",r.available?"true":"false",r.faulted?"true":"false",r.testing?"true":"false",(unsigned long)r.remaining_ms);
        return true;
    }
    if(!strcmp(line,"TELEMETRY")) {
        const bridge_t *host=host_bridge();
        xinput_pad_t raw=host->pad,processed={0}; uint8_t ignored[8],keys[20],output[20];
        if(!host->pad_valid) xinput_pad_clear(&raw);
        control_transform(control_current(),&raw,&processed,ignored);
        make_report(0,output);make_report(1,keys);
        char a[100],b[100];
        snprintf(a,sizeof(a),"[%u,%u,%u,%d,%d,%d,%d]",raw.buttons,raw.lt,raw.rt,raw.lx,raw.ly,raw.rx,raw.ry);
        snprintf(b,sizeof(b),"[%u,%u,%u,%d,%d,%d,%d]",processed.buttons,processed.lt,processed.rt,processed.lx,processed.ly,processed.rx,processed.ry);
        xinput_pad_t out={0};
        char wheel[72]="";
        if(XINPUT_ACTIVE) {
            (void)xinput_pad_parse_wired(output,20,&out);
        } else {
            uint16_t throttle=get_u16(output+2),brake=get_u16(output+4),buttons=get_u16(output+6);
            out.lx=(int16_t)get_u16(output);
            out.rt=xinput_axis_quantize(throttle);
            out.lt=xinput_axis_quantize(brake);
            out.buttons=(uint16_t)((buttons&0x03ffu)|((buttons&0x3c00u)<<2));
            snprintf(wheel,sizeof(wheel),",\"wheel\":[%d,%u,%u,%u]",out.lx,throttle,brake,buttons);
        }
        bool blocked=report_gate_blocked(&gate) || generation!=state->generation ||
                     !host_controls_released || boot_pending || switch_phase!=SWITCH_IDLE;
        snprintf(response,CONSOLE_RESPONSE_SIZE,
            "OK {\"raw\":%s,\"processed\":%s,\"output\":[%u,%u,%u,%d,%d,%d,%d],"
            "\"keys\":[%u,%u,%u,%u,%u,%u,%u,%u],\"state\":%d,\"age\":%lu,\"reports\":%lu,\"timeouts\":%lu,"
            "\"blocked\":%s,\"keyboard_rollover\":%s,\"fresh\":%s%s}\n",
            a,b,out.buttons,out.lt,out.rt,out.lx,out.ly,out.rx,out.ry,
            keys[0],keys[1],keys[2],keys[3],keys[4],keys[5],keys[6],keys[7],(int)host->state,
            (unsigned long)(host->pad_valid?(uint32_t)(time_us_64()/1000)-host->last_report_ms:0),
            (unsigned long)host->valid_reports,(unsigned long)host->timeouts,
            blocked?"true":"false",keys[2]==1?"true":"false",bridge_host_ready(host)?"true":"false",wheel);
        return true;
    }
#endif
    return false;
}
bool pedal_usb_feed(console_input_t *input,char ch,pedal_t *pedal,console_save_fn save,void *context,char response[CONSOLE_RESPONSE_SIZE]) {
    if(pedal_usb_boot_pending()
#if PEDAL_USB_HOST
       || pedal_usb_switch_pending()
#endif
    ) {
        memset(input,0,sizeof(*input));
        if(ch!='\n')return false;
        snprintf(response,CONSOLE_RESPONSE_SIZE,pedal_usb_boot_pending()?"ERR UPDATING\n":"ERR SWITCHING\n");return true;
    }
    if(!console_feed(input,ch,pedal,save,context,response)) return false;
    if(!strcmp(response,"ERR COMMAND\n") || !strcmp(response,"ERR STATE_OR_VALUE\n"))
        (void)pedal_usb_console(input->line,response);
    return true;
}
void pedal_usb_task(void) {
#if PEDAL_USB_HOST
    if(switch_phase==SWITCH_DETACHED) return;
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
    if(!tud_mounted() || tud_suspended()) {
#if PEDAL_USB_HOST
        host_rumble_enable(false);
#endif
        return;
    }
#if PEDAL_USB_HOST
    host_rumble_enable(state->armed && state->sample_valid && state->mode==PEDAL_JOYSTICK &&
                       state->calibration_axis<0 && !report_gate_blocked(&gate) && host_controls_released &&
                       !boot_pending && switch_phase==SWITCH_IDLE);
#endif
#if PEDAL_USB_XINPUT
    if(XINPUT_ACTIVE) xinput_device_task();
#endif
    uint64_t now=time_us_64(); if(now<next_report) return;
    next_report=now+1000;
    for(unsigned i=0;i<2;i++) {
#if PEDAL_USB_HOST
        if((boot_pending || pedal_usb_switch_pending()) && !gate.pending[i])continue;
#endif
        uint8_t hid_instance=(uint8_t)i;
        unsigned len=i?8:4,first=0;
#if PEDAL_USB_XINPUT
        if(XINPUT_ACTIVE) {
            hid_instance=0;
            if(i==0) { len=20;first=2;if(!xinput_device_ready())continue; }
        } else if(i==0) len=WHEEL_REPORT_SIZE;
        if((!XINPUT_ACTIVE || i!=0) && !tud_hid_n_ready(hid_instance))continue;
#else
        if(!tud_hid_n_ready(hid_instance))continue;
#endif
        if(gate.busy[i])continue;
        uint8_t data[20]; make_report(i,data);
        bool neutral=true; for(unsigned j=first;j<len;j++) if(data[j]) neutral=false;
        if(!report_gate_begin(&gate,i,neutral))continue;
        bool sent;
#if PEDAL_USB_XINPUT
        if(XINPUT_ACTIVE && i==0) {
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
    if(XINPUT_ACTIVE) {
        if(instance==0)report_gate_complete(&gate,1);
    } else {
#if PEDAL_USB_HOST
        if(instance==0 && len==WHEEL_REPORT_SIZE)
            last_xinput_controlled_neutral=!report[2] && !report[3] && !report[4] && !report[5] && !report[6] && !report[7];
#endif
        report_gate_complete(&gate,instance);
    }
#else
    report_gate_complete(&gate,instance);
#endif
}
#if PEDAL_USB_XINPUT
void xinput_device_output_report(const uint8_t report[8]) {
#if PEDAL_USB_HOST
    host_rumble_receive(report);
#else
    (void)report;
#endif
}
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
    if(XINPUT_ACTIVE) {
        if(instance!=0)return 0;
        make_report(1,data);len=8;
    } else {
        if(instance>=2)return 0;
        make_report(instance,data);len=instance?8:WHEEL_REPORT_SIZE;
    }
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
    return XINPUT_ACTIVE?xinput_device_descriptor:usb_wheel_device_descriptor;
#else
    return usb_device_descriptor;
#endif
}
const uint8_t *tud_descriptor_configuration_cb(uint8_t index) {
    if(index!=0)return NULL;
#if PEDAL_USB_XINPUT
    return XINPUT_ACTIVE?xinput_configuration_descriptor:usb_wheel_configuration_descriptor;
#else
    return usb_configuration_descriptor;
#endif
}
const uint8_t *tud_hid_descriptor_report_cb(uint8_t instance) {
#if PEDAL_USB_XINPUT
    if(XINPUT_ACTIVE)return instance==0?usb_keyboard_descriptor:NULL;
    return instance==0?usb_wheel_descriptor:instance==1?usb_keyboard_descriptor:NULL;
#else
    return instance==0?usb_joystick_descriptor:instance==1?usb_keyboard_descriptor:NULL;
#endif
}
const uint16_t *tud_descriptor_string_cb(uint8_t index,uint16_t langid) {
    (void)langid; static uint16_t out[33]; char serial[2*PICO_UNIQUE_BOARD_ID_SIZE_BYTES+1];
#if PEDAL_USB_HOST
    if(index==0xee)return XINPUT_ACTIVE?xinput_os_string:NULL;
    const char *strings[]={"","DIY Pedals",XINPUT_ACTIVE?"RP2350 XInput Bridge":"RP2350 Racing Wheel",serial};
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
