#include "host.h"
#include "xinput_protocol.h"
#include "tusb.h"
#include "host/usbh_pvt.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
const usbh_class_driver_t *usbh_app_driver_get_cb(uint8_t *count);
void tuh_mount_cb(uint8_t addr);
void tuh_umount_cb(uint8_t addr);
static const usbh_class_driver_t *driver;
static uint64_t now;
static bool busy[256],fail_start;
static uint8_t *input,*output;
static uint8_t sent[8];
static unsigned output_count;
static unsigned aborts;
bool tuh_edpt_abort_xfer(uint8_t addr,uint8_t ep) {CHECK(addr==1 && ep==2 && busy[ep]);busy[ep]=false;aborts++;return true;}
uint64_t get_absolute_time(void) {return now;}
bool tusb_init(uint8_t port,const tusb_rhport_init_t *cfg) {CHECK(port==1 && cfg->role==TUSB_ROLE_HOST);return true;}
bool tuh_configure(uint8_t port,uint32_t id,const void *cfg) {CHECK(port==1 && id==TUH_CFGID_RPI_PIO_USB_CONFIGURATION && *(const uint8_t *)cfg==12);return true;}
void tuh_task(void) {}
bool tuh_edpt_open(uint8_t addr,const tusb_desc_endpoint_t *ep) {(void)ep;CHECK(addr==1);return true;}
bool tuh_vid_pid_get(uint8_t addr,uint16_t *vid,uint16_t *pid) {CHECK(addr==1);*vid=0x20bc;*pid=0x5128;return true;}
bool tuh_control_xfer(tuh_xfer_t *x) {x->result=XFER_RESULT_SUCCESS;x->actual_len=x->setup->wLength;x->complete_cb(x);return true;}
bool usbh_edpt_busy(uint8_t addr,uint8_t ep) {CHECK(addr==1);return busy[ep];}
bool usbh_edpt_claim(uint8_t addr,uint8_t ep) {CHECK(addr==1);return !busy[ep];}
void usbh_edpt_release(uint8_t addr,uint8_t ep) {CHECK(addr==1);busy[ep]=false;}
bool usbh_edpt_xfer(uint8_t addr,uint8_t ep,uint8_t *buffer,uint16_t size) {
    CHECK(addr==1 && !busy[ep]);if(fail_start && ep==2)return false;busy[ep]=true;
    if(ep==0x81){CHECK(size==32);input=buffer;}
    else {CHECK(ep==2 && size==8);output=buffer;memcpy(sent,buffer,8);output_count++;}
    return true;
}
void usbh_driver_set_config_complete(uint8_t addr,uint8_t itf) {CHECK(addr==1 && itf==0);}
bool tud_cdc_connected(void) {return false;}
bool tud_inited(void) {return true;}
uint32_t tud_cdc_write(const void *data,uint32_t size) {(void)data;return size;}
void tud_cdc_write_flush(void) {}
static void tick(void){now++;host_task();}
static void ack(bool ok){CHECK(busy[2]);busy[2]=false;CHECK(driver->xfer_cb(1,2,ok?XFER_RESULT_SUCCESS:XFER_RESULT_FAILED,ok?8:0));}
static void pad(void){memset(input,0,20);input[1]=20;busy[0x81]=false;CHECK(driver->xfer_cb(1,0x81,XFER_RESULT_SUCCESS,20));}
static void attach(void){
    uint8_t descriptor[40];memcpy(descriptor,xinput_configuration_descriptor+9,40);descriptor[33+2]=2;
    CHECK(driver->open(1,1,(const tusb_desc_interface_t *)descriptor,40));CHECK(driver->set_config(1,0));tuh_mount_cb(1);
    tick();tick();pad();pad();CHECK(host_ready());tick();
    if(busy[2]){CHECK(!sent[3] && !sent[4]);ack(true);}
    host_rumble_enable(true);
}
static void init(void){uint8_t count;driver=usbh_app_driver_get_cb(&count);CHECK(count==1);CHECK(driver->init());host_init();attach();}
static void relay(void){
    init();uint8_t command[8]={0,8,0,120,230,0,0,0};unsigned n=output_count;
    host_rumble_receive(command);tick();CHECK(output_count==n+1 && !memcmp(sent,command,8));
    command[3]=42;command[4]=11;host_rumble_receive(command);CHECK(output[3]==120 && output[4]==230);tick();CHECK(output_count==n+1);
    ack(true);tick();CHECK(sent[3]==42 && sent[4]==11);ack(true);
    const uint8_t stop[8]={0,8,0,0,0,0,0,0};host_rumble_receive(stop);tick();CHECK(!memcmp(sent,stop,8));ack(true);
    host_rumble_status_t status;host_rumble_status(&status);CHECK(status.received==3 && status.sent>=3 && !status.pending && !status.in_flight);
}
static void faults(void){
    init();uint8_t command[8]={0,8,0,200,100,0,0,0};host_rumble_receive(command);tick();ack(true);
    host_rumble_enable(false);tick();CHECK(!sent[3] && !sent[4]);ack(true);
    unsigned n=output_count;host_rumble_receive(command);tick();CHECK(output_count==n);
    host_rumble_enable(true);tick();CHECK(output_count==n); /* no replay on resume */
    host_rumble_receive(command);tick();ack(true);now+=251;tick();CHECK(!sent[3] && !sent[4]);ack(true);
    tuh_umount_cb(1);driver->close(1);memset(busy,0,sizeof(busy));host_rumble_receive(command);attach();tick();CHECK(!sent[3] && !sent[4]);
}
static void retries(void){
    init();uint8_t command[8]={0,8,0,90,80,0,0,0};host_rumble_receive(command);fail_start=true;tick();
    fail_start=false;now+=25;tick();CHECK(sent[3]==90);ack(false);now+=25;tick();CHECK(sent[3]==90);ack(true);
    host_rumble_status_t s;host_rumble_status(&s);CHECK(s.errors>=2 && !s.pending);
    command[3]=100;host_rumble_receive(command);tick();host_rumble_stop();ack(false);tick();CHECK(!sent[3] && !sent[4]);ack(true);
}
static void stalled(void){
    init();uint8_t command[8]={0,8,0,100,200,0,0,0};host_rumble_receive(command);tick();CHECK(busy[2]);
    host_rumble_stop();tick();CHECK(aborts==1 && !busy[2]);
    /* A completion queued before abort must not complete a newer OUT. */
    driver->xfer_cb(1,2,XFER_RESULT_SUCCESS,8);
    tick();CHECK(busy[2] && !sent[3] && !sent[4]);ack(true);
    host_rumble_receive(command);tick();now+=101;tick();CHECK(aborts==2 && !busy[2]);
}
static void flood(void){
    init();uint8_t command[8]={0,8,0,100,200,0,0,0};
    for(unsigned i=0;i<3;i++) {
        host_rumble_receive(command);tick();CHECK(busy[2]);
        command[3]++;host_rumble_receive(command);ack(false);
        unsigned n=output_count;host_rumble_receive(command);tick();
        if(i<2) CHECK(output_count==n); /* New PC commands cannot bypass backoff. */
        now+=25;
    }
    if(!busy[2])tick();CHECK(busy[2] && !sent[3] && !sent[4]);
    ack(true);host_rumble_status_t s;host_rumble_status(&s);CHECK(s.errors>=3);
}
static void stop_priority(void){
    init();uint8_t command[8]={0,8,0,100,200,0,0,0};host_rumble_receive(command);tick();
    host_rumble_stop();command[3]=55;host_rumble_receive(command);tick();CHECK(aborts==1);
    tick();CHECK(!sent[3] && !sent[4]);ack(true);tick();CHECK(sent[3]==55 && sent[4]==200);ack(true);
}
static void exhausted(void){
    init();uint8_t command[8]={0,8,0,100,200,0,0,0};
    for(unsigned i=0;i<3;i++){host_rumble_receive(command);tick();ack(false);now+=25;}
    for(unsigned i=0;i<3;i++){tick();CHECK(!sent[3] && !sent[4]);ack(false);now+=25;}
    host_rumble_status_t s;host_rumble_status(&s);CHECK(s.faulted && !s.pending);
    unsigned n=output_count;
    for(unsigned i=0;i<10;i++){pad();host_rumble_receive(command);now+=25;tick();CHECK(output_count==n);}
}
bool host_rumble_test(uint8_t left,uint8_t right,uint32_t duration_ms);
static void timed_test(void){
    init();CHECK(!host_rumble_test(64,32,99));CHECK(!host_rumble_test(64,32,3001));
    CHECK(host_rumble_test(64,32,200));tick();CHECK(sent[3]==64 && sent[4]==32);ack(true);
    uint8_t game[8]={0,8,0,200,255,0,0,0};host_rumble_receive(game);tick();
    host_rumble_status_t status;host_rumble_status(&status);CHECK(status.left==64 && status.right==32);
    now+=180;pad();tick();CHECK(status.left==64);now+=20;pad();tick();
    host_rumble_status(&status);CHECK(!status.left && !status.right);
    CHECK(busy[2] && !sent[3] && !sent[4]);ack(true);tick();CHECK(!busy[2]); /* No replay of ignored game request. */
    host_rumble_receive(game);tick();CHECK(sent[3]==200);ack(true);
    CHECK(host_rumble_test(30,20,3000));tick();ack(true);host_rumble_stop();tick();
    CHECK(!sent[3] && !sent[4]);ack(true);
    host_rumble_enable(false);CHECK(!host_rumble_test(1,1,500));
}
static void timed_wrap(void){
    init();now=UINT32_MAX-100u;pad();tick();
    CHECK(host_rumble_test(50,60,200));tick();ack(true);now+=201;pad();tick();
    host_rumble_status_t status;host_rumble_status(&status);CHECK(!status.left && !status.right);
    CHECK(!sent[3] && !sent[4]);ack(true);
}
int main(int argc,char **argv){
    CHECK(argc==2);if(!strcmp(argv[1],"relay"))relay();else if(!strcmp(argv[1],"faults"))faults();else if(!strcmp(argv[1],"retries"))retries();else if(!strcmp(argv[1],"stalled"))stalled();else if(!strcmp(argv[1],"flood"))flood();else if(!strcmp(argv[1],"stop_priority"))stop_priority();else if(!strcmp(argv[1],"exhausted"))exhausted();
    else if(!strcmp(argv[1],"timed"))timed_test();else if(!strcmp(argv[1],"timed_wrap"))timed_wrap();else return 2;
    puts("PASS: real Host OUT relay, stable buffers, latest command, stop and reconnect");return 0;
}
