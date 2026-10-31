#include "pedal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)
static pedal_t ready(void) {
    pedal_config_t c; pedal_t p;
    pedal_defaults(&c);
    for (int i=0;i<PEDAL_AXES;i++) {
        c.axis[i].released=500; c.axis[i].pressed=3500;
        c.axis[i].calibrated=true; c.axis[i].window=1; c.axis[i].gamma=100;
    }
    pedal_init(&p,&c);
    uint16_t r[2]={500,500}; pedal_sample(&p,r);
    return p;
}
static void sample(pedal_t *p,uint16_t a,uint16_t b) { uint16_t r[2]={a,b}; pedal_sample(p,r); }
static void defaults(void) {
    pedal_config_t c; pedal_defaults(&c); CHECK(pedal_config_valid(&c));
    CHECK(!c.axis[0].calibrated && !c.axis[1].calibrated);
    CHECK(c.axis[0].on==300 && c.axis[0].off==100);
    CHECK(c.axis[1].gamma==200 && c.axis[0].window==4);
    pedal_t p; pedal_init(&p,&c); sample(&p,4095,4095);
    CHECK(p.output[0]==0 && p.output[1]==0);
}
static void mapping(void) {
    pedal_t p=ready(); sample(&p,3500,500); CHECK(p.output[0]==65535 && p.output[1]==0);
    sample(&p,4095,0); CHECK(p.output[0]==65535 && p.output[1]==0);
    p.config.axis[1].released=3500; p.config.axis[1].pressed=500;
    pedal_reset(&p); sample(&p,500,3500); sample(&p,500,500); CHECK(p.output[1]==65535);
    uint16_t previous=0; pedal_reset(&p); sample(&p,500,3500);
    for(int r=500;r<=3500;r++) { sample(&p,(uint16_t)r,3500); CHECK(p.output[0]>=previous); previous=p.output[0]; }
}
static void filtering(void) {
    pedal_t p=ready(); p.config.axis[0].window=4; pedal_reset(&p);
    sample(&p,500,500); CHECK(p.filtered[0]==500);
    sample(&p,3500,500); CHECK(p.filtered[0]==2000);
    sample(&p,3500,500); sample(&p,3500,500); sample(&p,3500,500);
    CHECK(p.filtered[0]==3500 && p.output[0]==65535);
}
static void hysteresis(void) {
    pedal_t p=ready(); sample(&p,560,500); CHECK(p.output[0]==0);
    sample(&p,590,500); CHECK(p.output[0]>0);
    sample(&p,560,500); CHECK(p.output[0]>0);
    sample(&p,530,500); CHECK(p.output[0]==0);
    sample(&p,560,500); CHECK(p.output[0]==0);
}
static void curve(void) {
    pedal_t p=ready(); p.config.axis[1].gamma=200;
    sample(&p,2000,2000); CHECK(p.output[0]>32000 && p.output[0]<33000);
    CHECK(p.output[1]>15500 && p.output[1]<16500);
    sample(&p,3500,3500); CHECK(p.output[1]==65535);
}
static void calibration(void) {
    pedal_t p=ready(); CHECK(pedal_cal_begin(&p,0)); CHECK(!pedal_cal_begin(&p,1));
    sample(&p,3500,3500); CHECK(p.output[0]==0 && p.output[1]==0);
    CHECK(p.cal_min==500 && p.cal_max==3500); CHECK(pedal_cal_end(&p));
    CHECK(p.config.axis[0].released==500 && p.config.axis[0].pressed==3500);
    sample(&p,3500,500); CHECK(p.output[0]==0); /* must release first */
    sample(&p,500,500); CHECK(pedal_cal_begin(&p,0)); sample(&p,510,500);
    CHECK(!pedal_cal_end(&p)); CHECK(p.config.axis[0].pressed==3500);
    pedal_cal_cancel(&p); CHECK(p.calibration_axis==-1);
    sample(&p,3500,500); CHECK(pedal_cal_begin(&p,0)); sample(&p,500,500);
    CHECK(pedal_cal_end(&p)); CHECK(p.config.axis[0].released==3500 && p.config.axis[0].pressed==500);
}
static void modes(void) {
    pedal_t p=ready(); uint8_t keys[8]; sample(&p,3500,3500);
    pedal_mode(&p,PEDAL_KEYBOARD); pedal_keyboard(&p,keys); CHECK(keys[2]==0);
    sample(&p,3500,3500); CHECK(!p.armed);
    sample(&p,500,500); CHECK(p.armed); sample(&p,3500,3500);
    pedal_keyboard(&p,keys); CHECK(keys[2]==26 && keys[3]==22);
    pedal_mode(&p,PEDAL_JOYSTICK); pedal_keyboard(&p,keys); CHECK(keys[2]==0 && keys[3]==0);
    p.config.axis[0].gamma=400;
    pedal_mode(&p,PEDAL_KEYBOARD); sample(&p,500,500);
    sample(&p,590,500); pedal_keyboard(&p,keys); CHECK(keys[2]==26);
    sample(&p,560,500); pedal_keyboard(&p,keys); CHECK(keys[2]==26);
    sample(&p,530,500); pedal_keyboard(&p,keys); CHECK(keys[2]==0);
}
static void invalid(void) {
    pedal_t p=ready(); pedal_config_t c=p.config;
    c.axis[0].pressed=c.axis[0].released; CHECK(!pedal_config_valid(&c)); CHECK(!pedal_apply(&p,&c));
    c=p.config; c.axis[0].on=c.axis[0].off; CHECK(!pedal_config_valid(&c));
    c=p.config; c.axis[0].gamma=0; CHECK(!pedal_config_valid(&c));
    c=p.config; c.axis[0].window=9; CHECK(!pedal_config_valid(&c));
    sample(&p,5000,500); CHECK(!p.sample_valid && !p.armed && p.output[0]==0);
    sample(&p,3500,500); CHECK(p.output[0]==0);
    sample(&p,500,500); sample(&p,3500,500); CHECK(p.output[0]==65535);
}
static void button(void) {
    pedal_button_t b={0}; CHECK(!pedal_button_update(&b,true,10));
    CHECK(!pedal_button_update(&b,false,20)); CHECK(!pedal_button_update(&b,true,30));
    CHECK(!pedal_button_update(&b,true,60)); CHECK(!pedal_button_update(&b,true,1559));
    CHECK(pedal_button_update(&b,true,1560)); CHECK(!pedal_button_update(&b,true,9000));
    CHECK(!pedal_button_update(&b,false,9010)); CHECK(!pedal_button_update(&b,false,9040));
    b=(pedal_button_t){0}; CHECK(!pedal_button_update(&b,true,0xfffffff0u));
    CHECK(!pedal_button_update(&b,true,14)); CHECK(pedal_button_update(&b,true,1514));
}
int main(int argc,char **argv) {
    if(argc!=2) return 2;
    const char *names[]={"defaults","mapping","filtering","hysteresis","curve","calibration","modes","invalid","button"};
    void (*tests[])(void)={defaults,mapping,filtering,hysteresis,curve,calibration,modes,invalid,button};
    for(unsigned i=0;i<sizeof(names)/sizeof(names[0]);i++) if(strcmp(argv[1],names[i])==0) { tests[i](); puts("PASS"); return 0; }
    return 2;
}
