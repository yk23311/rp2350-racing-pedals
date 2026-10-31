#include "control_profile.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
int main(void) {
    control_profile_t c; control_defaults(&c); CHECK(control_profile_valid(&c));
    CHECK(control_current()->sticks[0].gamma==100);
    xinput_pad_t in={.buttons=0xf3ff,.lt=255,.rt=128,.lx=-32768,.ly=32767,.rx=12345,.ry=-12345},out;
    uint8_t keys[8]; control_transform(&c,&in,&out,keys);
    CHECK(memcmp(&in,&out,sizeof(in))==0); for(unsigned i=0;i<8;i++) CHECK(keys[i]==0);
    c.sticks[0].deadzone=2000; in.lx=3000; in.ly=3000;
    control_transform(&c,&in,&out,keys); CHECK(out.lx==0 && out.ly==0);
    in.lx=16384; in.ly=16384; control_transform(&c,&in,&out,keys);
    CHECK(out.lx==out.ly && out.lx>14000 && out.lx<15000);
    c.sticks[0].gamma=200; control_transform(&c,&in,&out,keys); CHECK(out.lx>8000 && out.lx<10000);
    c.sticks[0].invert=3; control_transform(&c,&in,&out,keys); CHECK(out.lx<0 && out.ly==out.lx);
    control_defaults(&c); c.sticks[0].invert=1; in.lx=-32768; in.ly=32767;
    control_transform(&c,&in,&out,keys); CHECK(out.lx==32767 && out.ly==32767);
    c.triggers[0].deadzone=2000; c.triggers[1].gamma=200; in.lt=51; in.rt=128;
    control_transform(&c,&in,&out,keys); CHECK(out.lt==0 && out.rt==64);
    in.lt=255; control_transform(&c,&in,&out,keys); CHECK(out.lt==255);
    control_defaults(&c); in.buttons=0x1001; c.bindings[0]=(control_binding_t){0,10}; c.bindings[10]=(control_binding_t){0,0};
    control_transform(&c,&in,&out,keys); CHECK(out.buttons==0x1001);
    in.buttons=1; control_transform(&c,&in,&out,keys); CHECK(out.buttons==0x1000);
    c.bindings[1]=(control_binding_t){0,10}; in.buttons=3; control_transform(&c,&in,&out,keys); CHECK(out.buttons==0x1000);
    c.bindings[0]=(control_binding_t){1,4}; c.bindings[1]=(control_binding_t){1,4}; c.bindings[2]=(control_binding_t){1,0xe1};
    in.buttons=7; control_transform(&c,&in,&out,keys); CHECK(out.buttons==0 && keys[0]==2 && keys[2]==4 && keys[3]==0);
    for(unsigned i=0;i<7;i++) c.bindings[i]=(control_binding_t){1,(uint8_t)(4+i)};
    c.bindings[7]=(control_binding_t){1,0xe0}; in.buttons=255;
    control_transform(&c,&in,&out,keys); CHECK(keys[0]==1); for(unsigned i=2;i<8;i++) CHECK(keys[i]==1);
    c.bindings[0]=(control_binding_t){2,0}; in.buttons=1; control_transform(&c,&in,&out,keys); CHECK(out.buttons==0 && keys[2]==0);
    in.buttons=0; control_transform(&c,&in,&out,keys); for(unsigned i=0;i<8;i++) CHECK(keys[i]==0);
    control_defaults(&c); c.sticks[0].deadzone=9501; CHECK(!control_profile_valid(&c));
    control_defaults(&c); c.sticks[0].invert=4; CHECK(!control_profile_valid(&c));
    control_defaults(&c); c.bindings[0]=(control_binding_t){0,14}; CHECK(!control_profile_valid(&c));
    puts("PASS: control defaults, radial curves, endpoints, snapshot mapping, union and rollover"); return 0;
}
