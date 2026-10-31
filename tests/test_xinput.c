#include "xinput_protocol.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1); } } while(0)
static void packet(void) {
    pedal_config_t config; pedal_t p; uint8_t report[20]; pedal_defaults(&config); pedal_init(&p,&config);
    xinput_report_build(&p,false,report); CHECK(report[0]==0 && report[1]==20);
    for(unsigned i=2;i<20;i++) CHECK(report[i]==0);
    p.armed=true;p.sample_valid=true;p.config.axis[0].calibrated=true;p.config.axis[1].calibrated=true;
    p.output[0]=65535; xinput_report_build(&p,false,report);CHECK(report[5]==255 && report[4]==0);
    p.output[1]=65535; xinput_report_build(&p,false,report);CHECK(report[4]==255 && report[5]==255);
    p.output[0]=32768; xinput_report_build(&p,false,report); CHECK(report[5]==128);
    uint8_t previous=0;
    for(unsigned n=0;n<=65535;n++) { p.output[0]=(uint16_t)n; xinput_report_build(&p,false,report);CHECK(report[5]>=previous);previous=report[5]; }
    xinput_report_build(&p,true,report);CHECK(!report[4] && !report[5]);
    p.mode=PEDAL_KEYBOARD;xinput_report_build(&p,false,report);CHECK(!report[4] && !report[5]);p.mode=PEDAL_JOYSTICK;
    p.calibration_axis=0;xinput_report_build(&p,false,report);CHECK(!report[4] && !report[5]);p.calibration_axis=-1;
    p.armed=false;xinput_report_build(&p,false,report);CHECK(!report[4] && !report[5]);p.armed=true;
    p.sample_valid=false;xinput_report_build(&p,false,report);CHECK(!report[4] && !report[5]);p.sample_valid=true;
    p.config.axis[0].calibrated=false;xinput_report_build(&p,false,report);CHECK(report[5]==0 && report[4]==255);
    for(unsigned i=2;i<20;i++) if(i!=4 && i!=5) CHECK(report[i]==0);
}
static void layout(void) {
    CHECK(xinput_device_descriptor[4]==0xef && xinput_device_descriptor[10]==0x12 && xinput_device_descriptor[11]==0x40);
    const uint8_t *cfg=xinput_configuration_descriptor;
    CHECK(cfg[2]==140 && cfg[3]==0 && cfg[4]==4);
    CHECK(cfg[14]==0xff && cfg[15]==0x5d && cfg[16]==1);
    CHECK(cfg[18]==17 && cfg[19]==0x21 && cfg[24]==0x81 && cfg[31]==1);
    bool ep[256]={false};unsigned interfaces=0,endpoints=0;
    for(unsigned i=0;i<XINPUT_CONFIG_SIZE;) {
        CHECK(cfg[i]>=2 && i+cfg[i]<=XINPUT_CONFIG_SIZE);
        if(cfg[i+1]==4) CHECK(cfg[i+2]==interfaces++);
        if(cfg[i+1]==5) {CHECK(!ep[cfg[i+2]]);ep[cfg[i+2]]=true;endpoints++;}
        i+=cfg[i];
    }
    CHECK(interfaces==4 && endpoints==6 && ep[0x81] && ep[1] && ep[0x82] && ep[0x83] && ep[4] && ep[0x84]);
    CHECK(xinput_os_string[0]==0x0312 && xinput_os_string[1]=='M' && xinput_os_string[7]=='0' && xinput_os_string[8]==0x20);
    CHECK(xinput_compatible_id[0]==40 && xinput_compatible_id[8]==1 && xinput_compatible_id[16]==0 && xinput_compatible_id[17]==1);
    CHECK(memcmp(xinput_compatible_id+18,"XUSB10\0\0",8)==0);
}
static void control(void) {
    uint8_t reply[64];
    CHECK(xinput_control_response(0xc0,0x20,0,4,reply)==40 && memcmp(reply,xinput_compatible_id,40)==0);
    CHECK(xinput_control_response(0xc1,1,0x100,0,reply)==20 && reply[4]==255 && reply[5]==255);
    for(unsigned i=2;i<20;i++) if(i!=4 && i!=5) CHECK(reply[i]==0);
    CHECK(xinput_control_response(0xc1,1,0,0,reply)==8 && reply[3]==0 && reply[4]==0);
    CHECK(xinput_control_response(0xc1,1,0x100,1,reply)==-1);
    CHECK(xinput_control_response(0xc0,0x20,0,5,reply)==-1);
    CHECK(xinput_control_response(0x40,0x20,0,4,reply)==-1);
    CHECK(xinput_control_response(0xc1,99,0,0,reply)==-1);
}
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    if(!strcmp(argv[1],"packet")) packet();
    else if(!strcmp(argv[1],"layout"))layout();
    else if(!strcmp(argv[1],"control"))control();
    else return 2;
    puts("PASS");return 0;
}
