#include "control_record.h"
#include "config_record.h"
#include <string.h>

static uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0]|((uint16_t)p[1]<<8)); }
static uint32_t get32(const uint8_t *p) { return (uint32_t)get16(p)|((uint32_t)get16(p+2)<<16); }
static void put16(uint8_t *p,uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
static void put32(uint8_t *p,uint32_t v) { put16(p,(uint16_t)v); put16(p+2,(uint16_t)(v>>16)); }
static uint32_t crc32(const uint8_t *data,size_t size) {
    uint32_t crc=0xffffffffu;
    for(size_t i=0;i<size;i++) {
        crc^=data[i];
        for(unsigned j=0;j<8;j++) crc=(crc>>1)^((crc&1)?0xedb88320u:0u);
    }
    return ~crc;
}
bool control_record_encode(const pedal_config_t *pedal,const control_profile_t *profile,uint32_t sequence,uint8_t out[CONTROL_RECORD_SIZE]) {
    if(!pedal_config_valid(pedal) || !control_profile_valid(profile)) return false;
    memset(out,0xff,CONTROL_RECORD_SIZE); memcpy(out,"PDL2",4);
    put16(out+4,2); put16(out+6,CONTROL_RECORD_SIZE); put32(out+8,sequence);
    for(unsigned i=0;i<2;i++) {
        const pedal_axis_config_t *a=&pedal->axis[i]; uint8_t *p=out+12+12*i;
        put16(p,a->released); put16(p+2,a->pressed); put16(p+4,a->on); put16(p+6,a->off);
        put16(p+8,a->gamma); p[10]=a->window; p[11]=a->calibrated?1:0;
        p=out+36+6*i; put16(p,profile->sticks[i].deadzone); put16(p+2,profile->sticks[i].gamma); p[4]=profile->sticks[i].invert; p[5]=0;
        p=out+48+4*i; put16(p,profile->triggers[i].deadzone); put16(p+2,profile->triggers[i].gamma);
    }
    for(unsigned i=0;i<CONTROL_BUTTONS;i++) { out[56+2*i]=profile->bindings[i].kind; out[57+2*i]=profile->bindings[i].target; }
    put32(out+252,crc32(out,252)); return true;
}
bool control_record_decode(const uint8_t *data,size_t size,pedal_config_t *pedal,control_profile_t *profile,uint32_t *sequence) {
    if(size<4) return false;
    if(memcmp(data,"PDL1",4)==0) {
        if(!config_decode(data,size,pedal,sequence)) return false;
        control_defaults(profile); return true;
    }
    if(size<CONTROL_RECORD_SIZE || memcmp(data,"PDL2",4) || get16(data+4)!=2 || get16(data+6)!=CONTROL_RECORD_SIZE || get32(data+252)!=crc32(data,252)) return false;
    pedal_config_t candidate={0}; control_profile_t control; control_defaults(&control);
    for(unsigned i=0;i<2;i++) {
        const uint8_t *p=data+12+12*i; pedal_axis_config_t *a=&candidate.axis[i];
        if(p[11]>1) return false;
        a->released=get16(p); a->pressed=get16(p+2); a->on=get16(p+4); a->off=get16(p+6);
        a->gamma=get16(p+8); a->window=p[10]; a->calibrated=p[11]!=0;
        p=data+36+6*i; control.sticks[i].deadzone=get16(p); control.sticks[i].gamma=get16(p+2); control.sticks[i].invert=p[4];
        p=data+48+4*i; control.triggers[i].deadzone=get16(p); control.triggers[i].gamma=get16(p+2);
    }
    for(unsigned i=0;i<CONTROL_BUTTONS;i++) { control.bindings[i].kind=data[56+2*i]; control.bindings[i].target=data[57+2*i]; }
    if(!pedal_config_valid(&candidate) || !control_profile_valid(&control)) return false;
    *pedal=candidate; *profile=control; *sequence=get32(data+8); return true;
}
int control_record_select(const uint8_t *a,size_t na,const uint8_t *b,size_t nb,pedal_config_t *pedal,control_profile_t *profile,uint32_t *sequence) {
    pedal_config_t ca,cb; control_profile_t pa,pb; uint32_t sa=0,sb=0;
    bool va=control_record_decode(a,na,&ca,&pa,&sa),vb=control_record_decode(b,nb,&cb,&pb,&sb);
    if(!va && !vb) return -1;
    uint32_t delta=sb-sa;
    if(vb && (!va || (delta && delta<0x80000000u))) { *pedal=cb; *profile=pb; *sequence=sb; return 1; }
    *pedal=ca; *profile=pa; *sequence=sa; return 0;
}
