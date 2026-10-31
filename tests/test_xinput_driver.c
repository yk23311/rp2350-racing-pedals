#include "xinput_device.h"
#include "xinput_protocol.h"
#include "device/usbd_pvt.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1); } } while(0)
const usbd_class_driver_t *usbd_app_driver_get_cb(uint8_t *count);
bool tud_vendor_control_xfer_cb(uint8_t port,uint8_t stage,const tusb_control_request_t *request);
static bool busy[256],mounted=true,fail_send,fail_open_out;
static uint8_t *in_buffer,*out_buffer,*control_buffer;
static uint16_t control_length;
static unsigned success_count,failure_count,closed;
bool tud_ready(void) { return mounted; }
bool usbd_edpt_open(uint8_t p,const tusb_desc_endpoint_t *d) { CHECK(p==0);return !(d->bEndpointAddress==1 && fail_open_out); }
void usbd_edpt_close(uint8_t p,uint8_t ep) { CHECK(p==0 && ep==0x81);closed++; }
bool usbd_edpt_claim(uint8_t p,uint8_t ep) { CHECK(p==0);return !busy[ep]; }
bool usbd_edpt_release(uint8_t p,uint8_t ep) { CHECK(p==0);busy[ep]=false;return true; }
bool usbd_edpt_busy(uint8_t p,uint8_t ep) { CHECK(p==0);return busy[ep]; }
bool usbd_edpt_xfer(uint8_t p,uint8_t ep,uint8_t *b,uint16_t n) {
    CHECK(p==0 && !busy[ep]);if(fail_send)return false;busy[ep]=true;
    if(ep==0x81) { CHECK(n==20);in_buffer=b; } else { CHECK(ep==1 && n==32);out_buffer=b; }
    return true;
}
bool tud_control_xfer(uint8_t p,const tusb_control_request_t *r,void *b,uint16_t n) {
    CHECK(p==0);control_buffer=b;control_length=n<r->wLength?n:r->wLength;return true;
}
void xinput_device_report_complete(bool success) { if(success)success_count++;else failure_count++; }
void xinput_device_get_report(uint8_t b[20]) { memset(b,0,20);b[1]=20;b[5]=99; }
int main(void) {
    uint8_t count=0;const usbd_class_driver_t *driver=usbd_app_driver_get_cb(&count);CHECK(count==1);
    driver->init();CHECK(!xinput_device_ready());
    const tusb_desc_interface_t *itf=(const tusb_desc_interface_t *)(xinput_configuration_descriptor+9);
    CHECK(driver->open(0,itf,39)==0);
    tusb_desc_interface_t wrong=*itf;wrong.bInterfaceClass=3;CHECK(driver->open(0,&wrong,sizeof(wrong))==0);
    fail_open_out=true;CHECK(driver->open(0,itf,40)==0 && closed==1);fail_open_out=false;
    CHECK(driver->open(0,itf,40)==40 && xinput_device_ready());
    uint8_t report[20]={0,20};report[5]=255;CHECK(xinput_device_send(report));
    report[5]=0;CHECK(in_buffer[5]==255 && !xinput_device_ready());CHECK(!xinput_device_send(report));
    busy[0x81]=false;driver->xfer_cb(0,0x81,XFER_RESULT_SUCCESS,20);CHECK(success_count==1);
    CHECK(xinput_device_ready());fail_send=true;CHECK(!xinput_device_send(report));fail_send=false;
    CHECK(xinput_device_send(report));busy[0x81]=false;driver->xfer_cb(0,0x81,XFER_RESULT_FAILED,0);CHECK(failure_count==1);
    xinput_device_task();CHECK(out_buffer && busy[1]);out_buffer[0]=1;out_buffer[1]=3;out_buffer[2]=6;
    busy[1]=false;driver->xfer_cb(0,1,XFER_RESULT_SUCCESS,3);xinput_device_task();CHECK(busy[1]);
    tusb_control_request_t led={0xa1,1,0x101,0,3};
    CHECK(driver->control_xfer_cb(0,CONTROL_STAGE_SETUP,&led));CHECK(control_length==3 && control_buffer[0]==1 && control_buffer[1]==3 && control_buffer[2]==6);
    led=(tusb_control_request_t){0x21,9,0x200,0,3};CHECK(driver->control_xfer_cb(0,0,&led));
    control_buffer[0]=1;control_buffer[1]=3;control_buffer[2]=7;
    CHECK(driver->control_xfer_cb(0,CONTROL_STAGE_DATA,&led));
    led=(tusb_control_request_t){0xa1,1,0x101,0,3};CHECK(driver->control_xfer_cb(0,0,&led));CHECK(control_buffer[2]==7);
    tusb_control_request_t req={0xc0,0x20,0,4,16};
    CHECK(tud_vendor_control_xfer_cb(0,CONTROL_STAGE_SETUP,&req));CHECK(control_length==16 && control_buffer[0]==40);
    req=(tusb_control_request_t){0xc1,1,0x100,0,20};CHECK(tud_vendor_control_xfer_cb(0,0,&req));CHECK(control_length==20 && control_buffer[4]==255 && control_buffer[2]==0xff && control_buffer[3]==0xf3 && control_buffer[6]==0xff && control_buffer[7]==0x7f);
    req=(tusb_control_request_t){0xa1,1,0x100,0,20};CHECK(driver->control_xfer_cb(0,0,&req));CHECK(control_buffer[5]==99);
    req=(tusb_control_request_t){0x21,9,0x200,0,33};CHECK(!driver->control_xfer_cb(0,0,&req));
    req=(tusb_control_request_t){0x21,9,0x200,0,8};CHECK(driver->control_xfer_cb(0,0,&req));CHECK(control_length==8);
    req=(tusb_control_request_t){0xc1,99,0,0,64};CHECK(!tud_vendor_control_xfer_cb(0,0,&req));
    mounted=false;CHECK(!xinput_device_ready());mounted=true;
    driver->reset(0);CHECK(!xinput_device_ready());CHECK(driver->open(0,itf,40)==40 && xinput_device_ready());
    puts("PASS: native XInput endpoints, persistent buffers, failures, requests, reset");return 0;
}
