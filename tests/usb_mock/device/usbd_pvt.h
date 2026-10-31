#include "tusb.h"
typedef struct {
    const char *name;
    void (*init)(void);
    bool (*deinit)(void);
    void (*reset)(uint8_t port);
    uint16_t (*open)(uint8_t port,const tusb_desc_interface_t *desc,uint16_t length);
    bool (*control_xfer_cb)(uint8_t port,uint8_t stage,const tusb_control_request_t *request);
    bool (*xfer_cb)(uint8_t port,uint8_t address,xfer_result_t result,uint32_t length);
    void (*sof)(uint8_t port,uint32_t frame);
} usbd_class_driver_t;
bool usbd_edpt_open(uint8_t port,const tusb_desc_endpoint_t *desc);
void usbd_edpt_close(uint8_t port,uint8_t endpoint);
bool usbd_edpt_claim(uint8_t port,uint8_t endpoint);
bool usbd_edpt_release(uint8_t port,uint8_t endpoint);
bool usbd_edpt_busy(uint8_t port,uint8_t endpoint);
bool usbd_edpt_xfer(uint8_t port,uint8_t endpoint,uint8_t *buffer,uint16_t length);
