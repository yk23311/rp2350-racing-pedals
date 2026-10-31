#ifndef MOCK_TUSB_H
#define MOCK_TUSB_H
#include <stdint.h>
#include <stdbool.h>
typedef enum { XFER_RESULT_SUCCESS, XFER_RESULT_FAILED } xfer_result_t;
enum { CONTROL_STAGE_SETUP,CONTROL_STAGE_DATA,CONTROL_STAGE_ACK };
#pragma pack(push,1)
typedef struct { uint8_t bLength,bDescriptorType,bInterfaceNumber,bAlternateSetting,bNumEndpoints,bInterfaceClass,bInterfaceSubClass,bInterfaceProtocol,iInterface; } tusb_desc_interface_t;
typedef struct { uint8_t bLength,bDescriptorType,bEndpointAddress,bmAttributes; uint16_t wMaxPacketSize;uint8_t bInterval; } tusb_desc_endpoint_t;
typedef struct { uint8_t bmRequestType,bRequest;uint16_t wValue,wIndex,wLength; } tusb_control_request_t;
#pragma pack(pop)
bool tud_ready(void);
bool tud_control_xfer(uint8_t port,const tusb_control_request_t *request,void *buffer,uint16_t length);
typedef enum { HID_REPORT_TYPE_INPUT=1,HID_REPORT_TYPE_OUTPUT=2 } hid_report_type_t;
bool tusb_init(void);
void tud_task(void);
bool tud_mounted(void);
bool tud_suspended(void);
bool tud_hid_n_ready(uint8_t instance);
bool tud_hid_n_report(uint8_t instance,uint8_t report_id,const void *report,uint16_t length);
#endif
