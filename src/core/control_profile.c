#include "control_profile.h"
#include <math.h>
#include <string.h>

static const uint8_t button_bits[CONTROL_BUTTONS]={0,1,2,3,4,5,6,7,8,9,12,13,14,15};
void control_defaults(control_profile_t *p) {
    memset(p,0,sizeof(*p));
    for(unsigned i=0;i<2;i++) { p->sticks[i].gamma=100; p->triggers[i].gamma=100; }
    for(unsigned i=0;i<CONTROL_BUTTONS;i++) p->bindings[i].target=(uint8_t)i;
}
bool control_profile_valid(const control_profile_t *p) {
    if(!p) return false;
    for(unsigned i=0;i<2;i++) {
        const control_stick_t *s=&p->sticks[i]; const control_trigger_t *t=&p->triggers[i];
        if(s->deadzone>CONTROL_DEADZONE_MAX || s->gamma<CONTROL_GAMMA_MIN || s->gamma>CONTROL_GAMMA_MAX || s->invert>3 ||
           t->deadzone>CONTROL_DEADZONE_MAX || t->gamma<CONTROL_GAMMA_MIN || t->gamma>CONTROL_GAMMA_MAX) return false;
    }
    for(unsigned i=0;i<CONTROL_BUTTONS;i++) {
        const control_binding_t *b=&p->bindings[i];
        if(b->kind==0) { if(b->target>=CONTROL_BUTTONS) return false; }
        else if(b->kind==1) { if(b->target<4 || b->target>0xe7) return false; }
        else if(b->kind!=2 || b->target!=0) return false;
    }
    return true;
}
control_profile_t *control_current(void) {
    static control_profile_t current; static bool initialized;
    if(!initialized) { control_defaults(&current); initialized=true; }
    return &current;
}
static int16_t quantize(float value) {
    if(value>=32767.0f) return 32767;
    if(value<=-32768.0f) return -32768;
    return (int16_t)roundf(value);
}
static int16_t invert(int16_t value) { return value==-32768?32767:(int16_t)-value; }
static void stick(const control_stick_t *p,int16_t x,int16_t y,int16_t *ox,int16_t *oy) {
    *ox=x; *oy=y;
    if(p->deadzone || p->gamma!=100) {
        /* Use asymmetric XInput endpoints when normalizing; retain direction. */
        float fx=(float)x/(x<0?32768.0f:32767.0f),fy=(float)y/(y<0?32768.0f:32767.0f);
        float radius=sqrtf(fx*fx+fy*fy),dz=(float)p->deadzone/10000.0f;
        if(radius<=dz) { *ox=0; *oy=0; }
        else {
            float capped=fminf(radius,1.0f),mapped=powf((capped-dz)/(1.0f-dz),(float)p->gamma/100.0f);
            float scale=mapped/radius;
            *ox=quantize(fx*scale*(x<0?32768.0f:32767.0f));
            *oy=quantize(fy*scale*(y<0?32768.0f:32767.0f));
        }
    }
    if(p->invert&1) *ox=invert(*ox);
    if(p->invert&2) *oy=invert(*oy);
}
static uint8_t trigger(const control_trigger_t *p,uint8_t value) {
    if(!p->deadzone && p->gamma==100) return value;
    float x=(float)value/255.0f,dz=(float)p->deadzone/10000.0f;
    if(x<=dz) return 0;
    return (uint8_t)(powf((x-dz)/(1.0f-dz),(float)p->gamma/100.0f)*255.0f+0.5f);
}
void control_transform(const control_profile_t *p,const xinput_pad_t *input,xinput_pad_t *out,uint8_t keys[8]) {
    /* Snapshot also permits input==output without cascading button mappings. */
    xinput_pad_t in=*input; *out=in; out->buttons=0; memset(keys,0,8);
    stick(&p->sticks[0],in.lx,in.ly,&out->lx,&out->ly);
    stick(&p->sticks[1],in.rx,in.ry,&out->rx,&out->ry);
    out->lt=trigger(&p->triggers[0],in.lt); out->rt=trigger(&p->triggers[1],in.rt);
    bool usages[0xe0]={false}; unsigned count=0;
    for(unsigned i=0;i<CONTROL_BUTTONS;i++) if(in.buttons&(1u<<button_bits[i])) {
        const control_binding_t *b=&p->bindings[i];
        if(b->kind==0) out->buttons|=(uint16_t)(1u<<button_bits[b->target]);
        else if(b->kind==1) {
            if(b->target>=0xe0) keys[0]|=(uint8_t)(1u<<(b->target-0xe0));
            else if(!usages[b->target]) { usages[b->target]=true; count++; }
        }
    }
    if(count>6) memset(keys+2,1,6);
    else { unsigned at=2; for(unsigned i=4;i<0xe0;i++) if(usages[i]) keys[at++]=(uint8_t)i; }
}
