#include "usb_layout.h"
#include "report_gate.h"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1); } } while(0)
static void layout(void) {
    CHECK(usb_device_descriptor[0]==18 && usb_device_descriptor[1]==1);
    CHECK(usb_device_descriptor[4]==0xef && usb_configuration_descriptor[4]==4);
    CHECK(usb_configuration_descriptor[2]==125 && usb_configuration_descriptor[3]==0);
    unsigned interfaces=0,endpoints=0,hids=0; bool seen[256]={false};
    for(size_t pos=0;pos<125;) {
        const uint8_t *d=usb_configuration_descriptor+pos;
        CHECK(d[0]>=2 && pos+d[0]<=125);
        if(d[1]==4) { CHECK(d[2]==interfaces); interfaces++; }
        if(d[1]==5) { CHECK(!seen[d[2]]);seen[d[2]]=true;endpoints++; }
        if(d[1]==0x21) {
            size_t len=hids++?usb_keyboard_descriptor_size:usb_joystick_descriptor_size;
            CHECK((size_t)(d[7]|d[8]<<8)==len);
        }
        pos+=d[0];
    }
    CHECK(interfaces==4 && endpoints==5 && hids==2);
    /* Parse HID short global items, accounting for count and size at Input. */
    const uint8_t *desc[2]={usb_joystick_descriptor,usb_keyboard_descriptor};
    size_t lens[2]={usb_joystick_descriptor_size,usb_keyboard_descriptor_size};
    for(unsigned k=0;k<2;k++) {
        uint32_t bits=0,count=0,size=0,max=0;
        for(size_t pos=0;pos<lens[k];) {
            uint8_t tag=desc[k][pos++],n=tag&3; if(n==3)n=4;
            CHECK(pos+n<=lens[k]); uint32_t v=0;
            for(unsigned i=0;i<n;i++) v|=(uint32_t)desc[k][pos++]<<(8*i);
            switch(tag&0xfc) { case 0x24:max=v;break; case 0x74:size=v;break;case 0x94:count=v;break;case 0x80:bits+=count*size;break; }
        }
        CHECK(bits==(k?64u:32u)); if(k==0) CHECK(max==65535);
    }
}
static void gate(void) {
    report_gate_t g={0}; report_gate_reset(&g); CHECK(report_gate_blocked(&g));
    CHECK(!report_gate_begin(&g,0,false)); CHECK(report_gate_begin(&g,0,true));
    report_gate_complete(&g,0); CHECK(report_gate_blocked(&g));
    CHECK(report_gate_begin(&g,1,true)); report_gate_complete(&g,1); CHECK(!report_gate_blocked(&g));
    CHECK(report_gate_quiet(&g)); CHECK(report_gate_begin(&g,0,false)); CHECK(!report_gate_quiet(&g));
    report_gate_reset(&g); report_gate_complete(&g,0); CHECK(report_gate_blocked(&g));
    CHECK(report_gate_begin(&g,0,true)); report_gate_complete(&g,0);
    CHECK(report_gate_begin(&g,1,true)); report_gate_complete(&g,1); CHECK(report_gate_quiet(&g));
    CHECK(!report_gate_begin(&g,2,true));
}
int main(void) { layout();gate();puts("PASS: USB descriptor structure and neutral completion barrier");return 0; }
