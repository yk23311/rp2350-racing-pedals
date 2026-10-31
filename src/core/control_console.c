#include "control_profile.h"
#include <stdio.h>
#include <string.h>

static bool number(const char *s,uint16_t *out) {
    uint32_t value=0; if(!*s) return false;
    for(;*s;s++) {
        if(*s<'0' || *s>'9') return false;
        value=value*10u+(unsigned)(*s-'0'); if(value>65535) return false;
    }
    *out=(uint16_t)value; return true;
}
static void profile(char out[CONSOLE_RESPONSE_SIZE]) {
    const control_profile_t *p=control_current();
    int used=snprintf(out,CONSOLE_RESPONSE_SIZE,
        "OK {\"sticks\":[{\"deadzone\":%u,\"gamma\":%u,\"invert\":%u},{\"deadzone\":%u,\"gamma\":%u,\"invert\":%u}],"
        "\"triggers\":[{\"deadzone\":%u,\"gamma\":%u},{\"deadzone\":%u,\"gamma\":%u}],\"bindings\":[",
        p->sticks[0].deadzone,p->sticks[0].gamma,p->sticks[0].invert,p->sticks[1].deadzone,p->sticks[1].gamma,p->sticks[1].invert,
        p->triggers[0].deadzone,p->triggers[0].gamma,p->triggers[1].deadzone,p->triggers[1].gamma);
    for(unsigned i=0;i<CONTROL_BUTTONS;i++) used+=snprintf(out+used,CONSOLE_RESPONSE_SIZE-(size_t)used,
        "%s[%u,%u]",i?",":"",p->bindings[i].kind,p->bindings[i].target);
    snprintf(out+used,CONSOLE_RESPONSE_SIZE-(size_t)used,"]}\n");
}
bool control_console(pedal_t *p,const char *line,char out[CONSOLE_RESPONSE_SIZE]) {
    char buf[CONSOLE_LINE_SIZE],*tokens[6]; size_t length=strlen(line),count=0;
    if(length>=sizeof(buf)) return false;
    memcpy(buf,line,length+1); char *cursor=buf;
    while(*cursor) {
        while(*cursor==' ' || *cursor=='\t') cursor++;
        if(!*cursor) break;
        if(count==6) break;
        tokens[count++]=cursor;
        while(*cursor && *cursor!=' ' && *cursor!='\t') cursor++;
        if(*cursor) *cursor++=0;
    }
    if(!count) return false;
    bool query=strcmp(tokens[0],"PROFILE")==0,stick_cmd=strcmp(tokens[0],"STICK")==0;
    bool trigger_cmd=strcmp(tokens[0],"TRIGGER")==0,bind_cmd=strcmp(tokens[0],"BIND")==0;
    if(!query && !stick_cmd && !trigger_cmd && !bind_cmd) return false;
    snprintf(out,CONSOLE_RESPONSE_SIZE,"ERR STATE_OR_VALUE\n");
    if(query) { if(count==1) profile(out); return true; }
    size_t expected=stick_cmd?5:4;
    if(count!=expected || p->calibration_axis>=0) return true;
    uint16_t n[4]={0}; for(size_t i=1;i<count;i++) if(!number(tokens[i],&n[i-1])) return true;
    control_profile_t candidate=*control_current();
    if(stick_cmd) {
        if(n[0]>=2 || n[3]>3) return true;
        candidate.sticks[n[0]]=(control_stick_t){n[1],n[2],(uint8_t)n[3]};
    } else if(trigger_cmd) {
        if(n[0]>=2) return true;
        candidate.triggers[n[0]]=(control_trigger_t){n[1],n[2]};
    } else {
        if(n[0]>=CONTROL_BUTTONS || n[1]>2 || n[2]>255) return true;
        candidate.bindings[n[0]]=(control_binding_t){(uint8_t)n[1],(uint8_t)n[2]};
    }
    if(!control_profile_valid(&candidate)) return true;
    *control_current()=candidate; pedal_reset(p); snprintf(out,CONSOLE_RESPONSE_SIZE,"OK\n"); return true;
}
