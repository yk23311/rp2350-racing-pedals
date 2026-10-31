#include "console.h"
#include "control_profile.h"
#include <stdio.h>
#include <string.h>

static bool number(const char *s,uint16_t *value) {
    if(!*s) return false;
    uint32_t n=0;
    for(;*s;s++) {
        if(*s<'0' || *s>'9') return false;
        n=n*10u+(unsigned)(*s-'0');
        if(n>65535) return false;
    }
    *value=(uint16_t)n; return true;
}
static void status(const pedal_t *p,char *out) {
    const pedal_axis_config_t *a=&p->config.axis[0],*b=&p->config.axis[1];
    snprintf(out,CONSOLE_RESPONSE_SIZE,
        "OK {\"protocol\":1,\"usb_transport\":\"%s\",\"mode\":\"%s\",\"armed\":%s,\"calibration_axis\":%d,"
        "\"raw\":[%u,%u],\"filtered\":[%u,%u],\"output\":[%u,%u],\"axes\":["
        "{\"released\":%u,\"pressed\":%u,\"on\":%u,\"off\":%u,\"gamma\":%u,\"window\":%u,\"calibrated\":%s},"
        "{\"released\":%u,\"pressed\":%u,\"on\":%u,\"off\":%u,\"gamma\":%u,\"window\":%u,\"calibrated\":%s}]}\n",
        PEDAL_USB_XINPUT?"XINPUT":"HID",
        p->mode==PEDAL_KEYBOARD?"KEYBOARD":"JOYSTICK",p->armed?"true":"false",p->calibration_axis,
        p->raw[0],p->raw[1],p->filtered[0],p->filtered[1],p->output[0],p->output[1],
        a->released,a->pressed,a->on,a->off,a->gamma,a->window,a->calibrated?"true":"false",
        b->released,b->pressed,b->on,b->off,b->gamma,b->window,b->calibrated?"true":"false");
}
void console_execute(pedal_t *p,const char *line,console_save_fn save,void *context,char out[CONSOLE_RESPONSE_SIZE]) {
    char buf[CONSOLE_LINE_SIZE],*token[8]; size_t len=strlen(line),count=0;
    snprintf(out,CONSOLE_RESPONSE_SIZE,"ERR COMMAND\n");
    if(len>=sizeof(buf)) { snprintf(out,CONSOLE_RESPONSE_SIZE,"ERR TOO_LONG\n"); return; }
    if(control_console(p,line,out)) return;
    memcpy(buf,line,len+1);
    char *cursor=buf;
    while(*cursor) {
        while(*cursor==' ' || *cursor=='\t') cursor++;
        if(!*cursor) break;
        if(count==8) return;
        token[count++]=cursor;
        while(*cursor && *cursor!=' ' && *cursor!='\t') cursor++;
        if(*cursor) *cursor++=0;
    }
    if(count==0) return;
    bool ok=false;
    if(count==1 && strcmp(token[0],"GET")==0) { status(p,out); return; }
    if(count==2 && strcmp(token[0],"PING")==0) {
        if(strlen(token[1])!=32 || strspn(token[1],"0123456789abcdef")!=32) return;
        snprintf(out,CONSOLE_RESPONSE_SIZE,"OK {\"sync\":\"%s\"}\n",token[1]); return;
    }
    if(count==6 && strcmp(token[0],"SET")==0) {
        uint16_t n[5];
        for(unsigned i=0;i<5;i++) if(!number(token[i+1],&n[i])) return;
        if(n[0]>=PEDAL_AXES || n[4]>PEDAL_WINDOW_MAX) return;
        pedal_config_t candidate=p->config; pedal_axis_config_t *a=&candidate.axis[n[0]];
        a->on=n[1]; a->off=n[2]; a->gamma=n[3]; a->window=(uint8_t)n[4];
        ok=pedal_apply(p,&candidate);
    } else if(count==2 && strcmp(token[0],"MODE")==0) {
        if(strcmp(token[1],"JOYSTICK")==0) { pedal_mode(p,PEDAL_JOYSTICK); ok=true; }
        else if(strcmp(token[1],"KEYBOARD")==0) { pedal_mode(p,PEDAL_KEYBOARD); ok=true; }
    } else if(count==3 && strcmp(token[0],"CAL")==0) {
        uint16_t axis; if(!number(token[1],&axis) || axis>=PEDAL_AXES) return;
        if(strcmp(token[2],"BEGIN")==0) ok=pedal_cal_begin(p,axis);
        else if(p->calibration_axis==(int)axis) {
            if(strcmp(token[2],"END")==0) ok=pedal_cal_end(p);
            else if(strcmp(token[2],"CANCEL")==0) { pedal_cal_cancel(p); ok=true; }
        }
    } else if(count==1 && strcmp(token[0],"SAVE")==0) {
        if(p->calibration_axis<0 && p->armed && p->sample_valid && !p->output[0] && !p->output[1] && save) {
            ok=save(context,&p->config);
            if(ok) pedal_reset(p);
        }
    } else if(count==1 && strcmp(token[0],"DEFAULTS")==0) {
        pedal_config_t c; pedal_defaults(&c); ok=pedal_apply(p,&c);
    }
    snprintf(out,CONSOLE_RESPONSE_SIZE,ok?"OK\n":"ERR STATE_OR_VALUE\n");
}
bool console_feed(console_input_t *in,char ch,pedal_t *p,console_save_fn save,void *context,char out[CONSOLE_RESPONSE_SIZE]) {
    if(ch=='\r') return false;
    if(ch=='\n') {
        if(in->overflow) snprintf(out,CONSOLE_RESPONSE_SIZE,"ERR TOO_LONG_OR_BINARY\n");
        else { in->line[in->used]=0; console_execute(p,in->line,save,context,out); }
        in->used=0; in->overflow=false; return true;
    }
    if((unsigned char)ch<32 && ch!='\t') in->overflow=true;
    if(in->used>=sizeof(in->line)-1) in->overflow=true;
    if(!in->overflow) in->line[in->used++]=ch;
    return false;
}
