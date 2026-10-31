#include "pedal.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

void pedal_defaults(pedal_config_t *c) {
    memset(c,0,sizeof(*c));
    for(unsigned i=0;i<PEDAL_AXES;i++) {
        c->axis[i]=(pedal_axis_config_t){0,4095,300,100,i==1?200:100,4,false};
    }
}
bool pedal_config_valid(const pedal_config_t *c) {
    for(unsigned i=0;i<PEDAL_AXES;i++) {
        const pedal_axis_config_t *a=&c->axis[i];
        if(a->released>PEDAL_ADC_MAX || a->pressed>PEDAL_ADC_MAX ||
           abs((int)a->pressed-(int)a->released)<PEDAL_MIN_SPAN ||
           a->off>=a->on || a->on>5000 || a->gamma<100 || a->gamma>400 ||
           a->window<1 || a->window>PEDAL_WINDOW_MAX) return false;
    }
    return true;
}
void pedal_reset(pedal_t *p) {
    memset(p->filter,0,sizeof(p->filter));
    memset(p->output,0,sizeof(p->output));
    p->armed=false;
    p->generation++;
}
void pedal_init(pedal_t *p,const pedal_config_t *c) {
    memset(p,0,sizeof(*p));
    if(pedal_config_valid(c)) p->config=*c; else pedal_defaults(&p->config);
    p->calibration_axis=-1;
    pedal_reset(p);
}
bool pedal_apply(pedal_t *p,const pedal_config_t *c) {
    if(p->calibration_axis>=0 || !pedal_config_valid(c)) return false;
    p->config=*c;
    pedal_reset(p);
    return true;
}
static float travel(const pedal_axis_config_t *a,uint16_t raw) {
    float t=((float)raw-a->released)/((float)a->pressed-a->released);
    return t<0?0:t>1?1:t;
}
void pedal_sample(pedal_t *p,const uint16_t raw[PEDAL_AXES]) {
    memcpy(p->raw,raw,sizeof(p->raw));
    p->sample_valid=raw[0]<=PEDAL_ADC_MAX && raw[1]<=PEDAL_ADC_MAX;
    if(!p->sample_valid) { pedal_reset(p); return; }
    float t[PEDAL_AXES]; bool released=true;
    for(unsigned i=0;i<PEDAL_AXES;i++) {
        pedal_filter_t *f=&p->filter[i];
        const pedal_axis_config_t *a=&p->config.axis[i];
        if(f->count==a->window) f->sum-=f->samples[f->next]; else f->count++;
        f->samples[f->next]=raw[i]; f->sum+=raw[i];
        f->next=(uint8_t)((f->next+1)%a->window);
        p->filtered[i]=(uint16_t)(f->sum/f->count);
        t[i]=travel(a,p->filtered[i]);
        if(a->calibrated && t[i]>(float)a->off/10000.0f) released=false;
    }
    if(p->calibration_axis>=0) {
        uint16_t value=p->filtered[p->calibration_axis];
        if(value<p->cal_min) p->cal_min=value;
        if(value>p->cal_max) p->cal_max=value;
        memset(p->output,0,sizeof(p->output));
        return;
    }
    if(!p->armed && released) p->armed=true;
    for(unsigned i=0;i<PEDAL_AXES;i++) {
        const pedal_axis_config_t *a=&p->config.axis[i];
        pedal_filter_t *f=&p->filter[i];
        float off=(float)a->off/10000.0f;
        if(!p->armed || !a->calibrated) { p->output[i]=0; f->active=false; continue; }
        if(t[i]<=off) f->active=false;
        else if(t[i]>=(float)a->on/10000.0f) f->active=true;
        float x=f->active?(t[i]-off)/(1.0f-off):0.0f;
        p->output[i]=(uint16_t)(powf(x,(float)a->gamma/100.0f)*65535.0f+0.5f);
    }
}
bool pedal_cal_begin(pedal_t *p,unsigned axis) {
    if(axis>=PEDAL_AXES || p->calibration_axis>=0 || !p->sample_valid) return false;
    p->calibration_axis=(int)axis;
    p->cal_released=p->filtered[axis];
    p->cal_min=p->cal_max=p->cal_released;
    pedal_reset(p);
    return true;
}
bool pedal_cal_end(pedal_t *p) {
    if(p->calibration_axis<0 || !p->sample_valid) return false;
    unsigned i=(unsigned)p->calibration_axis;
    pedal_config_t candidate=p->config;
    candidate.axis[i].released=p->cal_released;
    candidate.axis[i].pressed=p->filtered[i];
    candidate.axis[i].calibrated=true;
    if(!pedal_config_valid(&candidate) || p->cal_max-p->cal_min<PEDAL_MIN_SPAN) return false;
    p->calibration_axis=-1;
    return pedal_apply(p,&candidate);
}
void pedal_cal_cancel(pedal_t *p) { p->calibration_axis=-1; pedal_reset(p); }
void pedal_mode(pedal_t *p,pedal_mode_t mode) {
    if((mode==PEDAL_JOYSTICK || mode==PEDAL_KEYBOARD) && p->mode!=mode) {
        p->mode=mode; pedal_cal_cancel(p);
    }
}
void pedal_keyboard(const pedal_t *p,uint8_t report[8]) {
    memset(report,0,8);
    if(p->mode!=PEDAL_KEYBOARD || !p->armed || p->calibration_axis>=0) return;
    unsigned k=2;
    if(p->config.axis[0].calibrated && p->filter[0].active) report[k++]=26;
    if(p->config.axis[1].calibrated && p->filter[1].active) report[k]=22;
}
bool pedal_button_update(pedal_button_t *b,bool down,uint32_t now) {
    if(down!=b->candidate) { b->candidate=down; b->changed_ms=now; }
    if(b->stable!=b->candidate && (uint32_t)(now-b->changed_ms)>=30) {
        b->stable=b->candidate;
        if(b->stable) b->pressed_ms=now; else b->fired=false;
    }
    if(b->stable && !b->fired && (uint32_t)(now-b->pressed_ms)>=1500) {
        b->fired=true; return true;
    }
    return false;
}
