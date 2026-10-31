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
        for(int j=0;j<8;j++) crc=(crc>>1)^((crc&1)?0xedb88320u:0u);
    }
    return ~crc;
}
bool config_encode(const pedal_config_t *c,uint32_t seq,uint8_t out[CONFIG_RECORD_SIZE]) {
    if(!pedal_config_valid(c)) return false;
    memcpy(out,"PDL1",4); put16(out+4,1); put16(out+6,CONFIG_RECORD_SIZE); put32(out+8,seq);
    for(unsigned i=0;i<PEDAL_AXES;i++) {
        uint8_t *p=out+12+12*i; const pedal_axis_config_t *a=&c->axis[i];
        put16(p,a->released); put16(p+2,a->pressed); put16(p+4,a->on);
        put16(p+6,a->off); put16(p+8,a->gamma); p[10]=a->window; p[11]=a->calibrated?1:0;
    }
    put32(out+36,crc32(out,36)); return true;
}
bool config_decode(const uint8_t *d,size_t n,pedal_config_t *c,uint32_t *seq) {
    if(n<CONFIG_RECORD_SIZE || memcmp(d,"PDL1",4) || get16(d+4)!=1 ||
       get16(d+6)!=CONFIG_RECORD_SIZE || get32(d+36)!=crc32(d,36)) return false;
    pedal_config_t candidate={0};
    for(unsigned i=0;i<PEDAL_AXES;i++) {
        const uint8_t *p=d+12+12*i; pedal_axis_config_t *a=&candidate.axis[i];
        if(p[11]>1) return false;
        a->released=get16(p); a->pressed=get16(p+2); a->on=get16(p+4);
        a->off=get16(p+6); a->gamma=get16(p+8); a->window=p[10]; a->calibrated=p[11]!=0;
    }
    if(!pedal_config_valid(&candidate)) return false;
    *c=candidate; *seq=get32(d+8); return true;
}
int config_select(const uint8_t *a,size_t na,const uint8_t *b,size_t nb,pedal_config_t *c,uint32_t *seq) {
    pedal_config_t ca,cb; uint32_t sa=0,sb=0;
    bool va=config_decode(a,na,&ca,&sa),vb=config_decode(b,nb,&cb,&sb);
    if(!va && !vb) return -1;
    uint32_t delta=sb-sa;
    if(vb && (!va || (delta!=0 && delta<0x80000000u))) { *c=cb; *seq=sb; return 1; }
    *c=ca; *seq=sa; return 0;
}
