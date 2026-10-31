#include "xinput_device.h"
#include "xinput_protocol.h"
#include "tusb.h"
#include "device/usbd_pvt.h"
#include <string.h>
/* App driver for MS-XUSBI, using the SDK-pinned TinyUSB endpoint API. */
static bool opened;
static uint32_t device_serial;
_Alignas(4) static uint8_t tx[20];
_Alignas(4) static uint8_t rx[32];
_Alignas(4) static uint8_t control_buffer[64];
static uint8_t led_report[3];
static void consume_output(const uint8_t *data,uint32_t length) {
    if(length==3 && data[0]==1 && data[1]==3 && data[2]<16)led_report[2]=data[2];
    /* Rumble commands are accepted but there are no physical motors. */
}
static void reset(uint8_t p) {
    (void)p;opened=false;memset(tx,0,sizeof(tx));tx[1]=20;memset(rx,0,sizeof(rx));
    led_report[0]=1;led_report[1]=3;led_report[2]=0;
}
static void init(void) { reset(0); }
static uint16_t open_itf(uint8_t p,const tusb_desc_interface_t *d,uint16_t n) {
    if(p!=0 || d->bInterfaceClass!=0xff || d->bInterfaceSubClass!=0x5d ||
       d->bInterfaceProtocol!=1 || d->bInterfaceNumber!=0 || d->bAlternateSetting!=0 ||
       d->bNumEndpoints!=2 || n<40) return 0;
    const uint8_t *bytes=(const uint8_t *)d;
    if(d->bLength!=9 || bytes[9]!=17 || bytes[10]!=0x21) return 0;
    const tusb_desc_endpoint_t *in=(const tusb_desc_endpoint_t *)(bytes+26);
    const tusb_desc_endpoint_t *out=(const tusb_desc_endpoint_t *)(bytes+33);
    if(in->bLength!=7 || out->bLength!=7 || in->bDescriptorType!=5 || out->bDescriptorType!=5 ||
       in->bEndpointAddress!=0x81 || out->bEndpointAddress!=1 ||
       ((const uint8_t *)in)[3]!=3 || ((const uint8_t *)out)[3]!=3 ||
       in->wMaxPacketSize!=32 || out->wMaxPacketSize!=32) return 0;
    if(!usbd_edpt_open(p,in)) return 0;
    if(!usbd_edpt_open(p,out)) { usbd_edpt_close(p,0x81);return 0; }
    opened=true;return 40;
}
static bool control(uint8_t p,uint8_t stage,const tusb_control_request_t *r) {
    if(r->wIndex!=0) return false;
    if(r->bmRequestType==0xa1 && r->bRequest==1 && r->wValue==0x100) {
        if(stage!=CONTROL_STAGE_SETUP)return true;
        xinput_device_get_report(control_buffer);
        return tud_control_xfer(p,r,control_buffer,20);
    }
    if(r->bmRequestType==0xa1 && r->bRequest==1 && r->wValue==0x101) {
        if(stage!=CONTROL_STAGE_SETUP)return true;
        memcpy(control_buffer,led_report,sizeof(led_report));
        return tud_control_xfer(p,r,control_buffer,sizeof(led_report));
    }
    if(r->bmRequestType==0x21 && r->bRequest==9 && r->wValue==0x200 && r->wLength<=32) {
        if(stage==CONTROL_STAGE_DATA) { consume_output(control_buffer,r->wLength);return true; }
        if(stage!=CONTROL_STAGE_SETUP)return true;
        return tud_control_xfer(p,r,control_buffer,r->wLength);
    }
    return false;
}
static bool xfer(uint8_t p,uint8_t ep,xfer_result_t result,uint32_t n) {
    (void)p;
    if(ep==0x81) { xinput_device_report_complete(result==XFER_RESULT_SUCCESS && n==20);return true; }
    if(ep==1) {
        if(result==XFER_RESULT_SUCCESS && n<=sizeof(rx))consume_output(rx,n);
        return true; /* OUT is re-armed by task, including after errors. */
    }
    return false;
}
static const usbd_class_driver_t driver={.name="XInput",.init=init,.reset=reset,.open=open_itf,.control_xfer_cb=control,.xfer_cb=xfer};
const usbd_class_driver_t *usbd_app_driver_get_cb(uint8_t *n) { *n=1;return &driver; }
bool xinput_device_ready(void) { return opened && tud_ready() && !usbd_edpt_busy(0,0x81); }
bool xinput_device_send(const uint8_t report[20]) {
    if(!xinput_device_ready() || !usbd_edpt_claim(0,0x81))return false;
    memcpy(tx,report,sizeof(tx));
    if(usbd_edpt_xfer(0,0x81,tx,sizeof(tx)))return true;
    usbd_edpt_release(0,0x81);return false;
}
void xinput_device_task(void) {
    if(!opened || !tud_ready() || usbd_edpt_busy(0,1) || !usbd_edpt_claim(0,1))return;
    if(!usbd_edpt_xfer(0,1,rx,sizeof(rx)))usbd_edpt_release(0,1);
}
void xinput_device_set_serial(uint32_t serial) { device_serial=serial; }
bool tud_vendor_control_xfer_cb(uint8_t p,uint8_t stage,const tusb_control_request_t *r) {
    if(stage!=CONTROL_STAGE_SETUP)return true;
    int length=xinput_control_response(r->bmRequestType,r->bRequest,r->wValue,r->wIndex,control_buffer);
    if(r->bmRequestType==0xc0 && r->bRequest==1 && r->wValue==0 && r->wIndex==0) {
        for(unsigned i=0;i<4;i++)control_buffer[i]=(uint8_t)(device_serial>>(i*8));
        length=4;
    }
    if(length<0)return false;
    return tud_control_xfer(p,r,control_buffer,(uint16_t)length);
}
