#include "xinput_protocol.h"
#include <string.h>
/* Wire formats: Microsoft MS-XUSBI 2.2.4.6 and 2.2.5.1.3. Development identity. */
const uint8_t xinput_device_descriptor[18]={
    18,1,0,2,0xef,2,1,64,0xfe,0xca,0x12,0x40,0,2,1,2,3,1
};
const uint8_t xinput_configuration_descriptor[XINPUT_CONFIG_SIZE]={
    9,2,140,0,4,1,0,0x80,50,
    9,4,0,0,2,0xff,0x5d,1,0,
    17,0x21,0,1,1,0x25,0x81,20,0,0,0,0,0x13,1,8,0,0,
    7,5,0x81,3,32,0,1,
    7,5,0x01,3,32,0,8,
    9,4,1,0,1,3,1,1,0,
    9,0x21,0x11,1,0,1,0x22,63,0,
    7,5,0x82,3,8,0,1,
    8,11,2,2,2,2,0,0,
    9,4,2,0,1,2,2,0,0,
    5,0x24,0,0x20,1,
    5,0x24,1,0,3,
    4,0x24,2,2,
    5,0x24,6,2,3,
    7,5,0x83,3,8,0,16,
    9,4,3,0,2,0x0a,0,0,0,
    7,5,4,2,64,0,0,
    7,5,0x84,2,64,0,0
};
const uint16_t xinput_os_string[9]={0x0312,'M','S','F','T','1','0','0',0x20};
const uint8_t xinput_compatible_id[40]={
    40,0,0,0,0,1,4,0,1,0,0,0,0,0,0,0,
    0,1,'X','U','S','B','1','0',0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0
};
void xinput_report_build(const pedal_t *p,bool neutral,uint8_t out[20]) {
    memset(out,0,20); out[1]=20;
    if(neutral || !p->armed || !p->sample_valid || p->calibration_axis>=0 || p->mode!=PEDAL_JOYSTICK) return;
    if(p->config.axis[0].calibrated) out[5]=(uint8_t)(((uint32_t)p->output[0]+128u)/257u);
    if(p->config.axis[1].calibrated) out[4]=(uint8_t)(((uint32_t)p->output[1]+128u)/257u);
}
int xinput_control_response(uint8_t t,uint8_t r,uint16_t v,uint16_t i,uint8_t out[64]) {
    if(t==0xc0 && r==0x20 && v==0 && i==4) { memcpy(out,xinput_compatible_id,40);return 40; }
    /* PC capabilities queries, also used by SDL's Xbox 360 backend. */
    if(t==0xc1 && r==1 && i==0 && v==0x100) {
        memset(out,0,20); out[1]=20; out[4]=out[5]=255; return 20;
    }
    if(t==0xc1 && r==1 && i==0 && v==0) {
        memset(out,0,8); out[1]=8;return 8; /* no physical rumble motors */
    }
    return -1;
}
