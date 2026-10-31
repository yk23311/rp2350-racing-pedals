#include "config_record.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
int main(void) {
    pedal_config_t c,d; uint8_t a[CONFIG_RECORD_SIZE],b[CONFIG_RECORD_SIZE],copy[CONFIG_RECORD_SIZE]; uint32_t seq;
    pedal_defaults(&c); c.axis[0].released=3500; c.axis[0].pressed=500; c.axis[0].calibrated=true;
    CHECK(config_encode(&c,0x12345678,a)); CHECK(memcmp(a,"PDL1",4)==0);
    CHECK(a[8]==0x78 && a[11]==0x12); CHECK(config_decode(a,sizeof(a),&d,&seq));
    CHECK(seq==0x12345678 && d.axis[0].released==3500 && d.axis[0].pressed==500 && d.axis[0].calibrated);
    CHECK(config_encode(&d,seq,copy)); CHECK(memcmp(a,copy,sizeof(a))==0);
    for(size_t i=0;i<sizeof(a);i++) { memcpy(copy,a,sizeof(a)); copy[i]^=1; CHECK(!config_decode(copy,sizeof(copy),&d,&seq)); }
    for(size_t n=0;n<sizeof(a);n++) CHECK(!config_decode(a,n,&d,&seq));
    CHECK(config_encode(&c,0xffffffffu,a)); CHECK(config_encode(&c,0,b));
    CHECK(config_select(a,sizeof(a),b,sizeof(b),&d,&seq)==1 && seq==0);
    b[10]^=1; CHECK(config_select(a,sizeof(a),b,sizeof(b),&d,&seq)==0);
    a[10]^=1; CHECK(config_select(a,sizeof(a),b,sizeof(b),&d,&seq)==-1);
    c.axis[0].window=0; CHECK(!config_encode(&c,0,a));
    puts("PASS: record roundtrip, corruption, truncation, wraparound, fallback"); return 0;
}
